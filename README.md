# Git Repository Migrator

A tool to migrate Git repositories (commits, tags, releases, and description) between GitHub repositories. Supports both CLI and GUI modes.

## Features
- Migrate all branches and tags
- Migrate GitHub releases (with token)
- Migrate repository description (with token)
- Retain commit authors
- Progress bar and status updates in GUI
- Select what to migrate (commits, tags, releases, description)
- Works with public and private repositories (token required for private)
- CLI/GUI integration

## Requirements
- Python 3.7+
- `requests` library
- `git` installed and available in PATH

Install Python dependencies:
```
pip install requests
```

## Usage

### GUI Mode
Launch the GUI:
```
python git_migrator.py --gui
```
Or simply:
```
python git_migrator.py
```

- Fill in the source and target repository URLs.
- (Optional) Enter your GitHub Personal Access Token for private repos, releases, or description migration.
- Select what you want to migrate using the checkboxes.
- Click **Start Migration**.
- Progress and status will be shown at the bottom.

### CLI Mode
Run from the command line:
```
python git_migrator.py <source_repo_url> <target_repo_url> [options]
```

#### Options
- `--token <token>`: GitHub personal access token (required for private repos, releases, or description)
- `--all`: Perform all actions in sequence
- `--migrate-releases`: Migrate GitHub releases (requires token)
- `--fetch-details`: Fetch repository description and commits (requires token)
- `--temp-dir <dir>`: Specify a custom temporary directory
- `--dry-run`: Simulate the migration without making changes
- `--verbose`: Enable verbose output

#### Example
```
python git_migrator.py https://github.com/source/repo https://github.com/target/repo --all --token <your_token>
```

## Notes
- For public repositories, you can migrate commits and tags without a token.
- For private repositories, releases, or description migration, a token with `repo` scope is required.
- The tool cleans up temporary files after migration.

## License
MIT
