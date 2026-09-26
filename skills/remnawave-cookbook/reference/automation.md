# Automating the fleet through the API

How the reference implementation drives the panel, the stack manager and the
secret store — and the rules that each cost an incident to learn. The
playbooks are in [`ansible-playbooks`](https://github.com/nargothrondir/ansible-playbooks)
(`playbooks/new-profile.yml`, `new-node.yml`, `dockhand-stack.yml`,
`enable-xhttp.yml`, `migrate-inbound-tags.yml`); the node stack is in
[`docker-stacks`](https://github.com/nargothrondir/docker-stacks)
(`remnanode/`).

## Rules

1. **Create external state through the tool's API, never by clicking.** A
   panel object, a stack variable, a template made by hand is absent from the
   next rebuild and from every review.
2. **Fetch, then guard.** GET the current state, mutate only what is missing.
   A write that fires on every run restarts Xray on every run.
3. **Find things by a stable key, never a display name.** People rename
   labels. Profile by name, node by address, host by the inbound it serves,
   inbound by tag — and a tag is the one key you must never change casually.
4. **Add, never rewrite.** A PATCH body is the current object plus what is
   missing: current config + new inbound, current squad inbounds + new uuid,
   current node inbounds + new uuid. Rebuilding from a template or from scratch
   removes whatever it did not know about.
5. **Assert what must not have changed.** After adding an inbound, check the
   existing ones kept their uuids. A failed assert is cheap; a silently
   re-created inbound cuts every user of it off.
6. **Keep secrets in a secret store, read at run time.** API tokens and the
   xHTTP path live there; tasks that touch them run with `no_log`.
7. **One node at a time, at an hour someone is awake.** Every profile change
   restarts Xray on that profile's nodes.

## Adding a protocol to a running profile

The order matters because each step is what the next depends on:

1. **Profile:** append the inbound (tag in the scheme; a socket `listen` for
   xHTTP) → Xray restarts on the profile's nodes.
2. **Squads:** add it to the squads that already carry the existing inbound.
3. **Host:** create one for the new inbound (it lands at the end of the list).
4. **Nodes:** add it to each node's `activeInbounds`.
5. **Node stack:** give the web server the xHTTP path (an environment variable
   that makes the location render) and redeploy.

Until step 5 the subscription entry exists but the node answers the path with
the decoy site. Existing users of the old protocol only notice the restart.

## Renaming tags safely

A rename is a delete and a create (`remnawave-2.8.md`). The migration:

1. Classify inbounds by what they are (protocol, network, security), not by
   their current names.
2. Refuse before changing anything if a target tag is already taken anywhere,
   two inbounds would get the same tag, or a routing rule names an old tag.
3. **Snapshot**, per new tag: squads, nodes (and whether each was switched on),
   hosts. Print it — the run's log is the recovery record.
4. PATCH the config with only the tags changed.
5. Re-bind **squads first** (an inbound in no squad reaches the node with no
   users), then nodes, then hosts.
6. Pause for the restart the panel queued, then **switch back on** the nodes it
   switched off meanwhile (only those that were on before).
7. Assert every inbound in the scheme has a squad, a node and a host, and every
   node that was on is on. A re-run with nothing to rename runs only this
   check, so an interrupted migration cannot look finished.
8. Recovery: re-run with the printed snapshot as input to re-bind without
   renaming again.

## Pitfalls in the automation itself

- **`delegate_to` and templated `ansible_host`.** Delegated tasks render the
  delegated host's variables with the TASK host's `inventory_hostname`. A
  group-wide `ansible_host: "{{ inventory_hostname }}.<mesh domain>"` sends
  `delegate_to: panel` to `controller.<mesh domain>` — an instant UNREACHABLE.
  Give a delegation target its address literally.
- **`no_log` hides the SSH error too.** An UNREACHABLE under `no_log` says
  nothing; re-run with `-vvv` and read the `ESTABLISH SSH CONNECTION` line for
  the real target.
- **A survey's empty optional field arrives as an empty string** that outranks
  play variables; test values with `default('', true)`, not `is defined`.
- **Stack environments are replaced as a whole list.** Keep every variable you
  did not mean to remove (send secrets back as the masked placeholder the API
  accepts), or a run without an option switches a feature off.
- **A config-only change to the web server needs a container restart**
  (`angie.md`); a changed environment variable recreates it by itself.
- **A secret store CLI call without its token fails with 403** at a
  preflight path that says nothing about the token; pass it explicitly.
