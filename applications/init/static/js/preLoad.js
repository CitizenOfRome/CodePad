function set_opacity(obj, alpha) {
    obj.style.opacity=alpha;
    if(typeof(obj.filters)!='undefined')   obj.filters.alpha.opacity = alpha*100;
}

function makeUnselectable(node) {
    //http://stackoverflow.com/questions/826782/css-rule-to-disable-text-selection-highlighting/4358620#4358620
    if (node.nodeType == 1) {
        node.unselectable = false;
    }
    var child = node.firstChild;
    while (child) {
        makeUnselectable(child);
        child = child.nextSibling;
    }
}


function getSelection(el) {
    //http://stackoverflow.com/questions/7190606/why-getting-a-text-selection-from-textarea-works-when-a-button-clicked-but-not-wh
    var start = 0, end = 0, normalizedValue, range, textInputRange, len, endRange;

    if (typeof el.selectionStart == "number" && typeof el.selectionEnd == "number") {
        start = el.selectionStart;
        end = el.selectionEnd;
    } else {
        range = document.selection.createRange();

        if (range && range.parentElement() == el) {
            len = el.value.length;
            normalizedValue = el.value.replace(/\r\n/g, "\n");

            // Create a working TextRange that lives only in the input
            textInputRange = el.createTextRange();
            textInputRange.moveToBookmark(range.getBookmark());

            // Check if the start and end of the selection are at the very end
            // of the input, since moveStart/moveEnd doesn't return what we want
            // in those cases
            endRange = el.createTextRange();
            endRange.collapse(false);

            if (textInputRange.compareEndPoints("StartToEnd", endRange) > -1) {
                start = end = len;
            } else {
                start = -textInputRange.moveStart("character", -len);
                start += normalizedValue.slice(0, start).split("\n").length - 1;

                if (textInputRange.compareEndPoints("EndToEnd", endRange) > -1) {
                    end = len;
                } else {
                    end = -textInputRange.moveEnd("character", -len);
                    end += normalizedValue.slice(0, end).split("\n").length - 1;
                }
            }
        }
    }
    if(start===0 && end===0)    return el.sel;
    return {start: start, end: end};
}

function setSelection(el, start, end) {
    //http://stackoverflow.com/questions/1981088/set-textarea-selection-in-internet-explorer
    el.focus();
    if (el.setSelectionRange) {
        el.setSelectionRange(start, end);
    }
    else if(el.createTextRange) {
        var normalizedValue = el.value.replace(/\r\n/g, "\n");

        start -= normalizedValue.slice(0, start).split("\n").length - 1;
        end -= normalizedValue.slice(0, end).split("\n").length - 1;

        range=el.createTextRange(); 
        range.collapse(true);
        range.moveEnd('character', end);
        range.moveStart('character', start); 
        range.select();
    }
    el.sel = {start: start, end: end};
}

function linech2n(ed, linech) {
    var line = linech.line;
    var ch = linech.ch;
    var n = line + ch; //for the \n s & chars in the line
    for(i=0;i<line;i++) {
        n += (ed.getLine(i)).length;//for the chars in all preceeding lines
    }
    return n;
}

function n2linech(ed, n) {
    var line=0, ch=0, index=0;
    for(i=0;i<ed.lineCount();i++) {
        len = (ed.getLine(i)).length;
        if(n < index+len) {
            //alert(len+","+index+","+(n-index));
            line = i;
            ch = n-index;
            return {line:line, ch:ch};
        }
        len++;//for \n char
        index += len;
    }
    return {line:line, ch:ch};
}