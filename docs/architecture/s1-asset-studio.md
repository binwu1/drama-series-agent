# S1 Asset Studio — preview / edit / upload / regenerate (Mode C)

Locked before S2. Complements [s1-enrich-contract.md](s1-enrich-contract.md).

## Placement

```text
enrich drafts
  → Asset Studio (this doc)
  → Accept (hash lock)
  → S2
```

**Mode C:** embedded Markdown editor (default) **and** OS external open + Reload.

## Literary

| Action | Tool | Side effect |
|--------|------|-------------|
| List | `list_literary_episodes` | status: draft / dirty / accepted |
| Read | `get_literary_episode` | |
| Save (embed) | `save_literary_episode` | invalidates literary Accept |
| Open external | `open_literary_external` / `open_literary_folder` | user edits on disk |
| Reload | Studio UI re-reads disk | |
| Import file | `import_literary_file` | + copy to `输入/`; invalidate |
| Regen | `run_literary_generate(episode_ids, revision_notes)` | invalidate |

## Cast

| Action | Tool | Side effect |
|--------|------|-------------|
| Wall | `list_cast_assets` | |
| Upload | `upload_cast_image` → `draft/` | invalidate cast Accept |
| Reject | `reject_cast_image` → `_history/` | invalidate |
| Regen | `run_cast_image_generate(..., revision_notes)` | invalidate |
| Open folder | `open_cast_folder` | |

Uploads always land in **draft**; Accept promotes to named anchors.

## Accept invalidation

Any save / upload / regenerate that changes content:

1. `invalidate_accept(scope=literary|cast|all)`
2. Append `status=superseded` decision
3. `s1_gate.ready_for_s2 = false`, stage back to `s1_enrich` if was `s2_ready`

## Web tabs

`web/components/hermes_accept_panel.py`:

1. Generate — one-liner + revision
2. Script Studio — embed editor + external + upload
3. Cast Studio — wall + upload + regen + reject
4. Accept — gate actions

## Chat (later)

Chat only milestones; edits happen in Studio or via tools above.
