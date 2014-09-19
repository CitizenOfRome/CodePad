function quoteUrl(url, safe) {
    if (typeof(safe) !== 'string') {
        safe = '/';    // Don't escape slashes by default
    }

    url = encodeURIComponent(url);

    // Unescape characters that were in the safe list
    toUnencode = [  ];
    for (var i = safe.length - 1; i >= 0; --i) {
        var encoded = encodeURIComponent(safe[i]);
        if (encoded !== safe.charAt(i)) {    // Ignore safe char if it wasn't escaped
            toUnencode.push(encoded);
        }
    }

    url = url.replace(new RegExp(toUnencode.join('|'), 'ig'), decodeURIComponent);

    return url;
}


var unquoteUrl = decodeURIComponent;
