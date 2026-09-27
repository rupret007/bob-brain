// Local PDFKit text extraction on macOS. Invoked with a path argument, no shell,
// automation targets, or network. The parent enforces the shared media deadline.
function run(argv) {
  ObjC.import("PDFKit");
  const document = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  if (!document || document.isNil() || document.isLocked) throw new Error("Unreadable PDF");
  let text = "";
  for (let index = 0; index < Math.min(Number(document.pageCount), 20); index++) {
    const value = document.pageAtIndex(index).string;
    if (value && !value.isNil()) text += ObjC.unwrap(value) + "\n";
    if (text.length > 1000000) break;
  }
  return text.slice(0, 1000000);
}
