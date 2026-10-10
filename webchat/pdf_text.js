// Local PDFKit text extraction on macOS. Invoked with a path argument, no shell,
// automation targets, or network. The parent enforces the shared media deadline.
function run(argv) {
  ObjC.import("PDFKit");
  const document = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  if (!document || document.isNil()) throw new Error("Unreadable PDF");
  if (document.isLocked) throw new Error("Password required");
  const totalPages = Number(document.pageCount);
  const maxPages = 20;
  const maxChars = 1000000;
  const pagesRead = Math.min(totalPages, maxPages);
  const pages = [];
  let totalChars = 0;
  for (let index = 0; index < pagesRead; index++) {
    const pageNum = index + 1;
    const value = document.pageAtIndex(index).string;
    let text = "";
    if (value && !value.isNil()) text = ObjC.unwrap(value);
    const empty = !String(text).trim();
    let slice = text;
    if (totalChars + slice.length > maxChars) {
      slice = slice.slice(0, Math.max(0, maxChars - totalChars));
    }
    totalChars += slice.length;
    pages.push({ page: pageNum, text: slice, empty: empty });
    if (totalChars >= maxChars) break;
  }
  return JSON.stringify({
    source: "pdfkit",
    total_pages: totalPages,
    pages_read: pages.length,
    pages: pages,
  });
}
