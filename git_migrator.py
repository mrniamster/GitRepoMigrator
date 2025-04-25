import subprocess
import argparse
import os
import sys
import requests  # Add this for GitHub API interactions
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from tkinter import ttk

def run_command(command, cwd=None, verbose=False):
    """Run a shell command and handle errors."""
    try:
        if verbose:
            print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)
        if verbose:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def clone_repo(source_url, temp_dir, verbose=False):
    """Clone the source repository."""
    print(f"Cloning repository from {source_url}...")
    run_command(["git", "clone", "--mirror", source_url, temp_dir], verbose=verbose)

def fetch_tags(temp_dir, verbose=False):
    """Fetch all tags from the source repository."""
    print("Fetching all tags...")
    run_command(["git", "fetch", "--tags"], cwd=temp_dir, verbose=verbose)

def add_target_remote(temp_dir, target_url, verbose=False):
    """Add target remote if it doesn't exist."""
    try:
        result = subprocess.run(["git", "remote"], cwd=temp_dir, capture_output=True, text=True)
        if "target" not in result.stdout.split():
            run_command(["git", "remote", "add", "target", target_url], cwd=temp_dir, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"Error checking remotes: {str(e)}")
        # If checking remotes fails, try adding it anyway but ignore if it exists
        try:
            run_command(["git", "remote", "add", "target", target_url], cwd=temp_dir, verbose=verbose)
        except subprocess.CalledProcessError as e:
            if "already exists" not in str(e.stderr):
                raise

def push_repo(temp_dir, target_url, verbose=False):
    """Push the repository to the target remote."""
    print(f"Pushing repository to {target_url}...")
    add_target_remote(temp_dir, target_url, verbose)
    # Push all branches and tags, excluding hidden references
    run_command(["git", "push", "--all", "target"], cwd=temp_dir, verbose=verbose)
    run_command(["git", "push", "--tags", "target"], cwd=temp_dir, verbose=verbose)

def push_tags(temp_dir, target_url, verbose=False):
    """Push all tags to the target repository."""
    print("Pushing all tags to the target repository...")
    add_target_remote(temp_dir, target_url, verbose)
    run_command(["git", "push", "--tags", "target"], cwd=temp_dir, verbose=verbose)

def migrate_github_releases(source_url, target_url, token, verbose=False):
    """Migrate GitHub releases from the source to the target repository."""
    print("Migrating GitHub releases...")
    headers = {"Authorization": f"token {token}"}
    
    # Extract owner and repo names from URLs
    def extract_owner_repo(url):
        parts = url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    source_owner, source_repo = extract_owner_repo(source_url)
    target_owner, target_repo = extract_owner_repo(target_url)

    # Fetch releases from the source repository
    source_releases_url = f"https://api.github.com/repos/{source_owner}/{source_repo}/releases"
    response = requests.get(source_releases_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch releases from {source_url}: {response.text}", file=sys.stderr)
        sys.exit(1)

    releases = response.json()
    if verbose:
        print(f"Found {len(releases)} releases in the source repository.")

    # Create releases in the target repository
    target_releases_url = f"https://api.github.com/repos/{target_owner}/{target_repo}/releases"
    for release in releases:
        release_data = {
            "tag_name": release["tag_name"],
            "name": release["name"],
            "body": release["body"],
            "draft": release["draft"],
            "prerelease": release["prerelease"]
        }
        if verbose:
            print(f"Migrating release: {release['name']} (tag: {release['tag_name']})")
        response = requests.post(target_releases_url, headers=headers, json=release_data)
        if response.status_code not in [200, 201]:
            print(f"Failed to create release in {target_url}: {response.text}", file=sys.stderr)
            sys.exit(1)

def fetch_repo_details(source_url, token, verbose=False):
    """Fetch repository description and all commits."""
    print("Fetching repository details...")
    headers = {"Authorization": f"token {token}"}

    # Extract owner and repo names from URL
    def extract_owner_repo(url):
        parts = url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    source_owner, source_repo = extract_owner_repo(source_url)

    # Fetch repository details
    repo_url = f"https://api.github.com/repos/{source_owner}/{source_repo}"
    response = requests.get(repo_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch repository details: {response.text}", file=sys.stderr)
        sys.exit(1)

    repo_details = response.json()
    description = repo_details.get("description", "No description provided")
    if verbose:
        print(f"Repository description: {description}")

    # Fetch all commits
    commits_url = f"https://api.github.com/repos/{source_owner}/{source_repo}/commits"
    response = requests.get(commits_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch commits: {response.text}", file=sys.stderr)
        sys.exit(1)

    commits = response.json()
    if verbose:
        print(f"Found {len(commits)} commits in the repository.")
        for commit in commits:
            print(f"Commit: {commit['sha']} - {commit['commit']['message']}")

    return description, commits

def update_repo_description(target_url, token, description, verbose=False):
    """Update the target repository's description."""
    print("Updating target repository description...")
    headers = {"Authorization": f"token {token}"}

    # Extract owner and repo names from URL
    def extract_owner_repo(url):
        parts = url.rstrip("/").split("/")
        return parts[-2], parts[-1]

    target_owner, target_repo = extract_owner_repo(target_url)

    # Update repository details
    repo_url = f"https://api.github.com/repos/{target_owner}/{target_repo}"
    response = requests.patch(repo_url, headers=headers, json={"description": description})
    if response.status_code not in [200, 201]:
        print(f"Failed to update repository description: {response.text}", file=sys.stderr)
        sys.exit(1)
    if verbose:
        print("Repository description updated successfully.")

def run_gui():
    def show_token_warning():
        """Show warning about features that require a token"""
        warning_message = """Warning: Running without a GitHub token. The following features will not be available:
- Repository description migration
- GitHub releases migration
- Private repository access

Only public repository commits and tags can be migrated without a token."""
        messagebox.showwarning("Token Not Provided", warning_message)

    def check_token_required_features():
        """Check if any selected features require a token"""
        if not token_entry.get():
            required_features = []
            if migrate_description_var.get():
                required_features.append("Repository Description Migration")
            if migrate_releases_var.get():
                required_features.append("GitHub Releases Migration")
            
            if required_features:
                error_message = f"The following selected features require a GitHub token:\n- " + "\n- ".join(required_features)
                messagebox.showerror("Token Required", error_message)
                return False
        return True

    def set_status(msg):
        status_var.set(msg)
        root.update_idletasks()

    def set_progress(val):
        progress_var.set(val)
        root.update_idletasks()

    def show_tooltip(widget, text):
        def on_enter(event):
            widget.tooltip = tk.Toplevel(widget)
            widget.tooltip.wm_overrideredirect(True)
            x = event.x_root + 10
            y = event.y_root + 10
            widget.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(widget.tooltip, text=text, background="#ffffe0", relief=tk.SOLID, borderwidth=1)
            label.pack()
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def start_migration():
        source_url = source_entry.get()
        target_url = target_entry.get()
        token = token_entry.get()
        temp_dir = temp_dir_entry.get()
        verbose = verbose_var.get()
        migrate_releases = migrate_releases_var.get()
        migrate_description = migrate_description_var.get()
        migrate_commits = migrate_commits_var.get()
        migrate_tags = migrate_tags_var.get()

        if not source_url or not target_url:
            messagebox.showerror("Error", "Source URL and Target URL are required.")
            return

        if not check_token_required_features():
            return

        if not token:
            show_token_warning()

        set_progress(0)
        set_status("Starting migration...")

        try:
            if not temp_dir:
                temp_dir = os.path.join(os.getcwd(), "temp_repo")

            # Clean up existing temp directory if it exists
            if os.path.exists(temp_dir):
                if verbose:
                    print(f"Cleaning up existing temporary directory: {temp_dir}")
                run_command(["rm", "-rf", temp_dir], verbose=verbose)

            step = 0
            total_steps = sum([migrate_description, migrate_commits, migrate_tags, migrate_releases]) + 2

            # Execute migration based on user selection
            if (migrate_description or migrate_commits) and token:
                try:
                    set_status("Fetching repository details...")
                    description, commits = fetch_repo_details(source_url, token, verbose=verbose)
                    step += 1
                    set_progress(int(100 * step / total_steps))
                    if migrate_description:
                        set_status("Updating target repository description...")
                        update_repo_description(target_url, token, description, verbose=verbose)
                        step += 1
                        set_progress(int(100 * step / total_steps))
                    if migrate_commits:
                        set_status("Fetched commits info.")
                        step += 1
                        set_progress(int(100 * step / total_steps))
                except Exception as e:
                    messagebox.showwarning("API Error", f"Failed to fetch repository details: {str(e)}\nContinuing with other operations...")

            if migrate_tags or migrate_commits:
                try:
                    set_status("Cloning repository...")
                    clone_repo(source_url, temp_dir, verbose=verbose)
                    step += 1
                    set_progress(int(100 * step / total_steps))
                    
                    if migrate_tags:
                        set_status("Fetching and pushing tags...")
                        fetch_tags(temp_dir, verbose=verbose)
                        push_tags(temp_dir, target_url, verbose=verbose)
                        step += 1
                        set_progress(int(100 * step / total_steps))

                    if migrate_commits:
                        set_status("Pushing repository branches...")
                        push_repo(temp_dir, target_url, verbose=verbose)
                        step += 1
                        set_progress(int(100 * step / total_steps))

                except Exception as e:
                    messagebox.showerror("Git Error", f"Failed during git operations: {str(e)}")
                    set_status("Error during git operations.")
                    set_progress(0)
                    return

            if migrate_releases and token:
                try:
                    set_status("Migrating GitHub releases...")
                    migrate_github_releases(source_url, target_url, token, verbose=verbose)
                    step += 1
                    set_progress(int(100 * step / total_steps))
                except Exception as e:
                    messagebox.showwarning("API Error", f"Failed to migrate releases: {str(e)}")

            set_progress(100)
            set_status("Migration completed successfully!")
            messagebox.showinfo("Success", "Migration completed successfully!")

        except Exception as e:
            set_status("Error during migration.")
            set_progress(0)
            messagebox.showerror("Error", str(e))
        finally:
            # Clean up temp directory
            if os.path.exists(temp_dir):
                try:
                    if verbose:
                        print(f"Cleaning up temporary directory: {temp_dir}")
                    run_command(["rm", "-rf", temp_dir], verbose=verbose)
                except Exception as e:
                    messagebox.showwarning("Warning", f"Failed to clean up temporary directory: {str(e)}")
            set_status("")
            set_progress(0)

    def browse_temp_dir():
        directory = filedialog.askdirectory()
        if directory:
            temp_dir_entry.delete(0, tk.END)
            temp_dir_entry.insert(0, directory)

    # Create the main window
    root = tk.Tk()
    root.title("Git Repository Migrator")
    root.resizable(True, True)
    
    # Frame for token warning
    warning_frame = tk.Frame(root, bg='#fff3cd')
    warning_frame.grid(row=0, column=0, columnspan=3, sticky='ew', padx=5, pady=5)
    warning_label = tk.Label(
        warning_frame, 
        text="Note: Token is optional but required for repository description, releases, and private repos",
        bg='#fff3cd',
        fg='#856404'
    )
    warning_label.pack(pady=5)

    # Source URL
    tk.Label(root, text="Source Repository URL:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
    source_entry = tk.Entry(root, width=50)
    source_entry.grid(row=1, column=1, padx=5, pady=5)

    # Target URL
    tk.Label(root, text="Target Repository URL:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
    target_entry = tk.Entry(root, width=50)
    target_entry.grid(row=2, column=1, padx=5, pady=5)

    # Token
    tk.Label(root, text="GitHub Personal Access Token:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
    token_entry = tk.Entry(root, width=50, show="*")
    token_entry.grid(row=3, column=1, padx=5, pady=5)

    # Temporary Directory
    tk.Label(root, text="Temporary Directory:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
    temp_dir_entry = tk.Entry(root, width=50)
    temp_dir_entry.grid(row=4, column=1, padx=5, pady=5)
    tk.Button(root, text="Browse", command=browse_temp_dir).grid(row=4, column=2, padx=5, pady=5)

    # Verbose
    verbose_var = tk.BooleanVar()
    tk.Checkbutton(root, text="Verbose Output", variable=verbose_var).grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)

    # Migration Options
    migrate_releases_var = tk.BooleanVar()
    migrate_releases_check = tk.Checkbutton(root, text="Migrate GitHub Releases", variable=migrate_releases_var)
    migrate_releases_check.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)

    migrate_description_var = tk.BooleanVar()
    migrate_description_check = tk.Checkbutton(root, text="Migrate Repository Description", variable=migrate_description_var)
    migrate_description_check.grid(row=7, column=1, sticky=tk.W, padx=5, pady=5)

    migrate_commits_var = tk.BooleanVar()
    tk.Checkbutton(root, text="Migrate Commits", variable=migrate_commits_var).grid(row=8, column=1, sticky=tk.W, padx=5, pady=5)

    migrate_tags_var = tk.BooleanVar()
    tk.Checkbutton(root, text="Migrate Tags", variable=migrate_tags_var).grid(row=9, column=1, sticky=tk.W, padx=5, pady=5)

    # Start Button
    tk.Button(root, text="Start Migration", command=start_migration).grid(row=10, column=1, pady=10)

    # Add progress bar and status label
    progress_var = tk.IntVar()
    status_var = tk.StringVar()
    progress = ttk.Progressbar(root, variable=progress_var, maximum=100)
    progress.grid(row=11, column=0, columnspan=3, sticky='ew', padx=5, pady=5)
    status_label = tk.Label(root, textvariable=status_var, anchor='w')
    status_label.grid(row=12, column=0, columnspan=3, sticky='ew', padx=5, pady=5)

    # Add tooltips for all options
    show_tooltip(source_entry, "URL of the source repository to migrate from.")
    show_tooltip(target_entry, "URL of the target repository to migrate to.")
    show_tooltip(token_entry, "GitHub token (required for private repos, releases, and description migration).")
    show_tooltip(temp_dir_entry, "Temporary directory for migration process.")
    show_tooltip(migrate_releases_check, "Migrate GitHub releases (requires token).")
    show_tooltip(migrate_description_check, "Migrate repository description (requires token).")

    root.mainloop()

# Update the main function to handle tokenless operations
def main():
    parser = argparse.ArgumentParser(description="Git Repository Migrator")
    parser.add_argument("--gui", action="store_true", help="Launch the GUI version of the tool")
    parser.add_argument("source", help="Source repository URL")
    parser.add_argument("target", help="Target repository URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate the migration without making changes")
    parser.add_argument("--temp-dir", help="Specify a custom temporary directory")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--token", help="GitHub personal access token for private repositories or releases migration")
    parser.add_argument("--migrate-releases", action="store_true", help="Migrate GitHub releases (requires --token)")
    parser.add_argument("--fetch-details", action="store_true", help="Fetch repository description and commits")
    parser.add_argument("--all", action="store_true", help="Perform all actions in sequence")
    args, unknown = parser.parse_known_args()

    if args.gui:
        run_gui()
        return

    source_url = args.source
    target_url = args.target
    temp_dir = args.temp_dir or os.path.join(os.getcwd(), "temp_repo")
    verbose = args.verbose
    token = args.token
    migrate_releases = args.migrate_releases

    if args.dry_run:
        print("Dry run mode enabled. No changes will be made.")
        print(f"Source repository: {source_url}")
        print(f"Target repository: {target_url}")
        print(f"Temporary directory: {temp_dir}")
        sys.exit(0)

    if not token:
        print("""
Warning: Running without a GitHub token. The following features will not be available:
- Repository description migration
- GitHub releases migration
- Private repository access

Only public repository commits and tags can be migrated without a token.
""")

    if args.all:
        print("Executing all actions in sequence...")
        # Fetch repository details and commits
        if token:
            description, commits = fetch_repo_details(source_url, token, verbose=verbose)
            print(f"Repository Description: {description}")
            print(f"Total Commits: {len(commits)}")

            # Update target repository description
            update_repo_description(target_url, token, description, verbose=verbose)
        else:
            print("Skipping fetching repository details and commits (requires --token).")

        # Clone and push the repository
        if os.path.exists(temp_dir):
            print(f"Cleaning up existing temporary directory: {temp_dir}")
            run_command(["rm", "-rf", temp_dir], verbose=verbose)

        try:
            clone_repo(source_url, temp_dir, verbose=verbose)
            fetch_tags(temp_dir, verbose=verbose)
            push_repo(temp_dir, target_url, verbose=verbose)
            push_tags(temp_dir, target_url, verbose=verbose)

            # Migrate GitHub releases
            if migrate_releases:
                if not token:
                    print("Error: --migrate-releases requires --token", file=sys.stderr)
                    sys.exit(1)
                migrate_github_releases(source_url, target_url, token, verbose=verbose)

            print("All actions completed successfully!")
        finally:
            if os.path.exists(temp_dir):
                print(f"Cleaning up temporary directory: {temp_dir}")
                run_command(["rm", "-rf", temp_dir], verbose=verbose)
        sys.exit(0)

    # Individual actions
    if args.fetch_details:
        if not token:
            print("Error: --fetch-details requires --token", file=sys.stderr)
            sys.exit(1)
        description, commits = fetch_repo_details(source_url, token, verbose=verbose)
        print(f"Repository Description: {description}")
        print(f"Total Commits: {len(commits)}")
        sys.exit(0)

    if os.path.exists(temp_dir):
        print(f"Cleaning up existing temporary directory: {temp_dir}")
        run_command(["rm", "-rf", temp_dir], verbose=verbose)

    try:
        # Clone and push the repository        
        clone_repo(source_url, temp_dir, verbose=verbose)
        fetch_tags(temp_dir, verbose=verbose)
        push_repo(temp_dir, target_url, verbose=verbose)
        push_tags(temp_dir, target_url, verbose=verbose)

        # Migrate GitHub releases if requested
        if migrate_releases:
            if not token:
                print("Error: --migrate-releases requires --token", file=sys.stderr)
                sys.exit(1)
            migrate_github_releases(source_url, target_url, token, verbose=verbose)

        print("Migration completed successfully!")
    finally:
        if os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            run_command(["rm", "-rf", temp_dir], verbose=verbose)

if __name__ == "__main__":
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] == "--gui"):
        run_gui()
    else:
        main()
