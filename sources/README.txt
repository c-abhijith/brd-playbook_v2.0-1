Memory workspaces only. Put every source here, one folder per type (the folder tells the agent what a file is):
  template/      client BRD templates (optional; without them the detailed defaults are used)
  databricks/    notes about Databricks workspaces and Genie (no tokens)
  metadata/      results of tools/metadata-extraction (CSV) + metadata-run-notes.md
  pipelines/     job and pipeline definitions (JSON)
  documents/     documents, slides, spreadsheets, image descriptions (as Markdown)
  team-brds/     earlier BRDs (treated as unconfirmed)
  agent-memory/  other agents' memory files and SQL / Databricks discovery packages
  inbox/         anything new after the memory is built, including memory-feedback.md files from BRD workspaces
Files over 1 MB or 20,000 lines: split them first (tools/split-large-files). Never put tokens, passwords or personal data here.
