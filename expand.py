## python expand.py pse-events.json -l 10 -o exp

## Imports
import os
import git
import sys
import argparse
import itertools
from pathlib import Path
import re
from datetime import datetime, timezone


## Module Constants
DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
EMPTY_TREE_SHA   = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def versions(path, count, branch='main'):
    """
    This function returns a generator which iterates through all commits of
    the repository located in the given path for the given branch. It yields
    file diff information to show a timeseries of file changes.
    """

    # Create the repository, raises an error if it isn't one.
    repo = git.Repo(path)
    assert not repo.bare

    # Iterate through the first N commits for the given branch in the repository
    # all indications are that they are in reverse chronological order by default
    # so we'll get the N most recent commits.
    for commit in repo.iter_commits(branch, max_count=count):
        # Determine the parent of the commit to diff against.
        # If no parent, this is the first commit, so use empty tree.
        # Then create a mapping of path to diff for each file changed.
        parent = commit.parents[0] if commit.parents else EMPTY_TREE_SHA
        diffs  = {
            diff.a_path: diff for diff in commit.diff(parent)
        }

        # The stats on the commit is a summary of all the changes for this
        # commit, we'll iterate through it to get the information we need.
        for objpath, stats in commit.stats.files.items():

            # Select the diff for the path in the stats
            diff = diffs.get(objpath)

            # If the path is not in the dictionary, it's because it was
            # renamed, so search through the b_paths for the current name.
            if not diff:
                for diff in diffs.values():
                    if diff.b_path == path and diff.renamed:
                        break

            # Update the stats with the additional information
            stats.update({
                'object': os.path.join(path, objpath),
                'commit': commit.hexsha,
                'author': commit.author.email,
                'timestamp': commit.authored_datetime.strftime(DATE_TIME_FORMAT),
                'size': diff_size(diff),
                'type': diff_type(diff),
            })

            yield stats


def diff_size(diff):
    """
    Computes the size of the diff by comparing the size of the blobs.
    """
    if diff.b_blob is None and diff.deleted_file:
        # This is a deletion, so return negative the size of the original.
        return diff.a_blob.size * -1

    if diff.a_blob is None and diff.new_file:
        # This is a new file, so return the size of the new value.
        return diff.b_blob.size

    # Otherwise just return the size a-b
    return diff.a_blob.size - diff.b_blob.size


def diff_type(diff):
    """
    Determines the type of the diff by looking at the diff flags.
    """
    if diff.renamed_file: return 'R'
    if diff.deleted_file: return 'D'
    if diff.new_file: return 'A'
    return 'M'


def count_versions(repo_path, rel_path, count, branch='main'):
    """
    Count the number of versions available for a given file without retrieving the actual content.
    Uses git log --follow to efficiently count commits that touched the file.
    Returns the count of versions found.
    """
    repo = git.Repo(repo_path)
    
    # Use repo.git.log with proper parameters
    result = repo.git.log(
        '--follow',
        '--oneline',
        '--format=%H',
        f'{branch}',
        '--',
        rel_path,
        n=count if count > 0 else None
    )
    
    if result:
        # Count non-empty lines (each line represents a commit)
        version_count = len([line for line in result.split('\n') if line.strip()])
    else:
        version_count = 0
        
    
    return version_count


def main():
    """
    Main function to run the script from the command line.
    Allows passing a path to a file to see its version history and export
    copies of the file at each commit, named with timestamp and original filename.
    """
    parser = argparse.ArgumentParser(description='Show version history of a file in a git repository and export file versions.')
    parser.add_argument('path', help='Path to the file to analyze')
    parser.add_argument('--branch', '-b', default='main', help='Git branch to analyze (default: main)')
    parser.add_argument('--repo', '-r', help='Path to the git repository (default: auto-detect)')
    parser.add_argument('--output-dir', '-o', help='Directory to save exported file versions (default: current directory)')
    parser.add_argument('--limit', '-l', type=int, help='Limit to the last N commits (default: all commits)')
    parser.add_argument('--count-only', '-c', action='store_true', help='Only count the number of versions available, do not export files')
    parser.add_argument('--start-datetime', '-s', help='Start date/time (UTC) to filter by in YYYY-MM-DDTHH:MM:SS-Z format (default: all time)')
    parser.add_argument('--end-datetime', '-e', help='End date/time (UTC) to filter by in YYYY-MM-DDTHH:MM:SS-Z format (default: all time)')
    args = parser.parse_args()

    if args.start_datetime:
        start_date_utc = datetime.strptime(args.start_datetime, DATE_TIME_FORMAT)
    else:
        start_date_utc = datetime.min.replace(tzinfo=timezone.utc)

    if args.end_datetime:
        end_date_utc = datetime.strptime(args.end_datetime, DATE_TIME_FORMAT)
    else:
        end_date_utc = datetime.now(timezone.utc)

    # Get the file path and make it absolute
    file_path = os.path.abspath(args.path)
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)
    
    # Determine the repository path
    repo_path = args.repo
    if not repo_path:
        # Try to find the git repository containing the file
        current_dir = os.path.dirname(file_path)
        while current_dir and current_dir != os.path.dirname(current_dir):
            if os.path.exists(os.path.join(current_dir, '.git')):
                repo_path = current_dir
                break
            current_dir = os.path.dirname(current_dir)
    
    if not repo_path:
        print(f"Error: Could not find a git repository for '{file_path}'.")
        sys.exit(1)
    
    # Get the relative path of the file within the repository
    rel_path = os.path.relpath(file_path, repo_path)
    
    # Set up output directory
    output_dir = args.output_dir or os.getcwd()
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Get the filename and extension for naming exported files
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    
    print(f"Analyzing version history for: {rel_path}")
    print(f"Repository: {repo_path}")
    print(f"Branch: {args.branch}")
    
    if args.count_only:
        print("Mode: Count only (no file export)")
    else:
        print(f"Exporting file versions to: {output_dir}")
    print("-" * 80)
    
    # Create the repository object
    repo = git.Repo(repo_path)
    print(f"using repo path: {repo_path}")

    if args.limit and args.limit > 0:
        print(f"Limiting to the last {args.limit} commits.")
    else:
        args.limit = -1
        print(f"no limit specified, analyzing all versions.")

    # Handle count-only mode
    if args.count_only and args.start_datetime is None and args.end_datetime is None:
        print(f"Counting versions of {rel_path}...")
        version_count = count_versions(repo_path, rel_path, args.limit, args.branch)
        print(f"Found {version_count} versions of '{rel_path}' in branch '{args.branch}'")
        if args.limit > 0:
            print(f"(searched through the last {args.limit} commits)")
        return

    # iterate through the versions to get all the stats, which will later be used for download
    # while doing so, filter by date
    file_versions = []
    print(f"iterating through versions of {rel_path}.")
    for stats in versions(repo_path, args.limit, args.branch):
        # Convert timestamp string back to datetime for comparison
        timestamp_dt = datetime.strptime(stats['timestamp'], DATE_TIME_FORMAT)
        # Convert to UTC for consistent timezone-aware comparison
        if timestamp_dt.tzinfo is None:
            timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
        else:
            timestamp_dt = timestamp_dt.astimezone(timezone.utc)
        if stats['object'].endswith(rel_path) and timestamp_dt >= start_date_utc and timestamp_dt <= end_date_utc:
            file_versions.append(stats)

    if args.count_only:
        print(f"Found {len(file_versions)} versions of '{rel_path}' in branch '{args.branch}' based on date range {start_date_utc} to {end_date_utc}")
        return

    # Display the results and export file versions
    if not file_versions:
        print(f"No version history found for '{rel_path}' in branch '{args.branch}'.")
    else:
        print(f"Found {len(file_versions)} versions:")
        for i, version in enumerate(file_versions, 1):
            print(f"{i}. {version['timestamp']} - {version['type']} - {version['author']}")
            print(f"   Commit: {version['commit']}")
            print(f"   Changes: +{version['insertions']} -{version['deletions']} lines")
            print(f"   Size change: {version['size']} bytes")
            
            # Skip deleted files
            if version['type'] == 'D':
                print(f"   File was deleted in this commit, skipping export.")
                print()
                continue
            
            # Create a safe filename with timestamp
            # Convert timestamp to a filename-safe format
            safe_timestamp = re.sub(r'[^0-9T-]', '', version['timestamp'])
            export_filename = f"{safe_timestamp}-{filename}"
            export_path = os.path.join(output_dir, export_filename)
            
            # Get the file content at this commit
            try:
                # Get the file content at this specific commit
                file_content = repo.git.show(f"{version['commit']}:{rel_path}")
                
                # Write the content to the export file
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                
                print(f"   Exported to: {export_filename}")
            except git.exc.GitCommandError:
                print(f"   Could not export file at this commit (possibly binary or renamed)")
            except Exception as e:
                print(f"   Error exporting file: {str(e)}")
            
            print()


if __name__ == "__main__":
    main()
