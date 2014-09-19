function get_mime_mode(filename) {
    ext = filename.split('.').pop();
    var extToMimes = {
       'html': 'htmlmixed',
       'htm': 'htmlmixed',
       'js': 'javascript',
       'json': 'javascript',
       'css': 'css',
       'xml': 'xml',
       'py': 'python',
       'pyw': 'python',
       'php': 'php',
       'php3': 'php',
       'phtml': 'php',
       'c': 'clike',
       'cc': 'clike',
       'cpp': 'clike',
       'java': 'clike',
       'hs': 'haskell',
       'lhs': 'haskell',
       'rb': 'ruby',
       'rbw': 'ruby',
       'yaml': 'yaml'
    }
    if (extToMimes.hasOwnProperty(ext)) {
        return extToMimes[ext];
    }
    return "";
}