"""
Mock Git Classes for Testing expand.py
Provides mock implementations of git operations
Test data is provided by separate test_data.py module
"""

from datetime import datetime


class MockGitCommandError(Exception):
    """Mock version of git.exc.GitCommandError"""
    pass


class MockGit:
    """Mock git command interface"""
    
    def __init__(self, mock_data):
        self.mock_data = mock_data
    
    def pull(self):
        """Mock git pull - does nothing"""
        print("Mock git pull executed")
        return "Already up to date."
    
    def log(self, *args, **kwargs):
        """Mock git log - returns predefined commit history"""
        commits = self.mock_data.get('commits', [])
        # Return formatted log output that matches expand.py's parsing
        log_lines = []
        for commit in commits:
            # Format: "hash message"
            log_lines.append(f"{commit['hash']} {commit['message']}")
        return '\n'.join(log_lines)
    
    def show(self, commit_file_spec):
        """Mock git show - returns predefined file content"""
        commit_hash, file_path = commit_file_spec.split(':', 1)
        
        # Find the commit and file content
        commits = self.mock_data.get('commits', [])
        for commit in commits:
            if commit['hash'].startswith(commit_hash[:8]):  # Match first 8 chars
                file_content = commit.get('files', {}).get(file_path)
                if file_content is not None:
                    return file_content
        
        # If not found, raise the mock error
        raise MockGitCommandError(f"Path '{file_path}' does not exist in '{commit_hash}'")


class MockCommit:
    """Mock git commit object"""
    
    def __init__(self, commit_data):
        self._commit_data = commit_data  # Store for later use
        self.hexsha = commit_data['hash']
        self.message = commit_data['message']
        self.committed_datetime = datetime.fromisoformat(commit_data['datetime'])
        self.authored_datetime = self.committed_datetime  # Same for simplicity
        self.parents = []  # Simplified for testing
        
        # Mock author
        self.author = type('MockAuthor', (), {'email': 'mock@test.com'})()
        
        # Mock stats (files changed in this commit)
        files = commit_data.get('files', {})
        self.stats = type('MockStats', (), {
            'files': {filename: {'insertions': 10, 'deletions': 5, 'lines': 15} 
                     for filename in files.keys()}
        })()
    
    def diff(self, other=None):
        """Mock diff method"""
        # Return mock diffs for each file in this commit
        files = self._commit_data.get('files', {})
        diffs = []
        for filename, content in files.items():
            # Create mock blobs with size property
            mock_a_blob = type('MockBlob', (), {'size': len(content) - 10})()  # Simulate smaller previous version
            mock_b_blob = type('MockBlob', (), {'size': len(content)})()       # Current version
            
            mock_diff = type('MockDiff', (), {
                'a_path': filename,
                'b_path': filename, 
                'renamed': False,
                'deleted_file': False,
                'new_file': False,
                'renamed_file': False,
                'a_blob': mock_a_blob,
                'b_blob': mock_b_blob
            })()
            diffs.append(mock_diff)
        return diffs


class MockRepo:
    """Mock git repository"""
    
    def __init__(self, path, mock_data=None):
        self.path = path
        self.bare = False
        self.mock_data = mock_data or get_default_mock_data()
        self.git = MockGit(self.mock_data)
        # Store mock data reference for easy access
        self._mock_data = self.mock_data
    
    def iter_commits(self, branch='main', max_count=None):
        """Mock commit iteration - returns predefined commits"""
        commits = self.mock_data.get('commits', [])
        if max_count:
            commits = commits[:max_count]
        
        for commit_data in commits:
            yield MockCommit(commit_data)


def get_default_mock_data():
    """Get default test scenario - delegates to test_data module"""
    try:
        from test_data import get_default_mock_data as get_test_data
        return get_test_data()
    except ImportError:
        # Fallback if test_data module isn't available
        return {
            'commits': [
                {
                    'hash': 'fallback123456',
                    'message': 'Fallback test data',
                    'datetime': '2024-01-15T18:00:00+00:00',
                    'files': {
                        'pse-events.json': '{"UnplannedOutageSummary": {"CustomerAfftectedCount": 1000}}'
                    }
                }
            ]
        }


if __name__ == "__main__":
    # Example usage / test
    print("Testing git mock classes...")
    repo = MockRepo("/fake/path")
    
    print(f"Mock repo created with {len(list(repo.iter_commits()))} commits")
    
    print("\nCommits:")
    for commit in repo.iter_commits(max_count=5):
        print(f"  {commit.hexsha[:8]} - {commit.message}")
    
    print(f"\nFile content at latest commit:")
    commits = list(repo.iter_commits(max_count=1))
    if commits:
        latest_commit = commits[0]
        try:
            content = repo.git.show(f"{latest_commit.hexsha}:pse-events.json")
            print(content[:200] + "...")
        except Exception as e:
            print(f"Could not show file content: {e}")
