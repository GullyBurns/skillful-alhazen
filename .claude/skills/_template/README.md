# Skill Template

This directory contains template files for creating new skills. Use these as a starting point when building a new domain skill.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Template for skill documentation (what Claude reads) |
| `template.py` | Template for CLI script (TypeDB operations) |
| `schema.tql` | Template for TypeDB schema (data model) |

## Quick Start

1. **Copy this directory:**
   ```bash
   cp -r .claude/skills/_template .claude/skills/<your-domain>
   ```

2. **Rename the script:**
   ```bash
   mv .claude/skills/<your-domain>/template.py .claude/skills/<your-domain>/<your-domain>.py
   ```

3. **Edit the schema (`schema.tql`):**
   - Replace `DOMAIN` with your domain name
   - Define your attributes, entities, and relations
   - Copy to `local_resources/typedb/namespaces/<your-domain>.tql`

4. **Edit the script (`<your-domain>.py`):**
   - Replace `DOMAIN` with your domain name
   - Implement your commands
   - Add argparse subcommands

5. **Edit `SKILL.md`:**
   - Fill in the frontmatter
   - Document your commands
   - Describe the sensemaking workflow

6. **Load the schema:**
   ```bash
   docker exec -i alhazen-typedb /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << 'EOF'
   transaction alhazen_notebook schema write
   source /schema/namespaces/<your-domain>.tql
   commit
   EOF
   ```

7. **Test:**
   ```bash
   uv run python .claude/skills/<your-domain>/<your-domain>.py --help
   ```

## Checklist

Before your skill is complete:

- [ ] Schema loaded into TypeDB
- [ ] Script has `--help` for all commands
- [ ] Script outputs JSON to stdout
- [ ] SKILL.md has complete command reference
- [ ] SKILL.md documents sensemaking workflow
- [ ] Tested with Claude Code

## Architecture Reference

See the wiki page [Skill-Architecture](https://github.com/GullyBurns/skillful-alhazen/wiki/Skill-Architecture) for detailed documentation on the three-component architecture.
