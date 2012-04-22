function get_mime_mode(filename) {
    ext = filename.split('.').pop();
    ext = ext.toLowerCase();
    var extToModes = {
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
       'yaml': 'yaml',
       'do': 'yaml'
    }
    if (extToModes.hasOwnProperty(ext)) {
        return extToModes[ext];
    }
    return "";
}