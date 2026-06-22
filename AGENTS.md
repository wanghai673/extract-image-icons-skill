# Repository guidance

- Treat `skills/extract-image-icons/` as the installable skill package.
- Keep `SKILL.md` concise and place detailed schemas or QA rules in `references/`.
- Use only the scripts bundled with this skill for its extraction workflow.
- Never weaken the visual-fidelity contract or report deterministic validation as proof of semantic fidelity.
- Run Python compilation and the bundled processor self-test before committing.
- Do not commit credentials, source images, generated asset sheets, extracted icons, or run directories.
