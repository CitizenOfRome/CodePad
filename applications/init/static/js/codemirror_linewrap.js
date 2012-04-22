// Adds extra \n chars to the specified text as needed and returns 
// the wrapped text 
myCodeMirror.getWrappedText = function (text, charsPerLine, wordWrapChars) {
    var lines = text.split("\n");
    var res = "";
    var reSplitChars = new RegExp(wordWrapChars.join("|"));

    for (var i = 0;i < lines.length;i++) {
      if (lines[i].length == 0) {// Empty line 
        res += "\n";
        continue;
      }

      var curPos = 0;
      while (curPos < lines[i].length) {
        var curStr = lines[i].substr(curPos, Math.min(lines[i].length - curPos, charsPerLine));
        var newPortion = "";
        if (curStr.length == charsPerLine) {// Enumerate chars from the end of the string to find breaking point 
          var posInString = curStr.length - 2;
          while (posInString > 0) {
            if (reSplitChars.test(curStr.charAt(posInString))) 
            {// Breaking char found 
              break;
            }
            posInString--;
          }
          if (posInString > 0) {// There was a breaking char in the string, catch it too 
            newPortion = curStr.substr(0, posInString + 1);
          }
          else {// No breaking chars found, take charsPerLine chars 
            newPortion = curStr;
          }
        }
        else {// The string is shorter than charsPerLine, no breaking needed 
          newPortion = curStr;
        }
        curPos += newPortion.length;
        // Don't append a line break after the last line 
        res += newPortion + (curPos >= lines[i].length - 1 && i == lines.length - 1 ? "" : "\n");
      }
    }

    return res;
};

// Word wraps the specified text range. Tabs are replaced with N spaces 
// according to options to provide correct chars width calculation. 
myCodeMirror.wordWrapRange = function (from, to) {
    var textToWrap = this.getRange(from, to);
    var tabReplacement = "";
    for (var i = 0;i < this.getOption("indentUnit");i++) {
      tabReplacement += " ";
    }
    textToWrap = textToWrap.replace(new RegExp("\t", "g"), tabReplacement);
    this.replaceRange(textToWrap, from, to);

    // Recalc "to" in case there were tabs in the text 
    to = this.absToRel(this.relToAbs(from) + textToWrap.length);

    // Get the needed width (in chars) 
    var charWidth = 8;// Default value 
    for (var i = from.line;i <= to.line;i++) {
      if (this.getLine(i).length > 1) {// Measure the actual char width 
        charWidth = (this.charCoords({line: i, ch: 1 }).x - this.charCoords({line: from.line, ch: 0 }).x);
        break;
      }
    }

    var gutter = this.getGutterElement();
    var charsPerLine = -2 + Math.round((this.getScrollerElement().clientWidth - (gutter != null ? gutter.clientWidth : 0)) / charWidth);

    // Make the wrap 
    var wrapChars = [",", "\\.", "\\(", "\\)", "\\s"].concat(this.getMode().wordWrapChars);
    var wrappedText = this.getWrappedText(textToWrap, charsPerLine, wrapChars);

    // Check whether the wrap will increase gutter width 
    var oldLinesCountLength = this.lineCount().toString().length;
    var constLinesCount = this.lineCount() - (to.line - from.line + 1);

    function getNewDigits(oldLinesCountLength, wrappedText) {
      return (constLinesCount + wrappedText.charCount("\n")).toString().length - oldLinesCountLength;
    }

    var newDigits = getNewDigits(oldLinesCountLength, wrappedText);
    while (newDigits > 0) {// Gutter will be increased after wrap, re-calc needed 
      charsPerLine -= newDigits;
      oldLinesCountLength += newDigits;
      wrappedText = this.getWrappedText(textToWrap, charsPerLine, wrapChars);
      newDigits = getNewDigits(oldLinesCountLength, wrappedText);
    }

    // Replace the range with wrapped text 
    this.operation(function () {
      myCodeMirror.replaceRange(wrappedText, from, to);
    });
};