// Local PDFKit rasterization, one requested page per invocation. No automation
// targets or network. Parent owns the private output file and shared deadline.
function run(argv) {
  try {
    ObjC.import("PDFKit");
    ObjC.import("AppKit");
  } catch (_) {
    return JSON.stringify({status: "unavailable"});
  }
  const fail = status => JSON.stringify({status: status});
  const number = Number(argv[1]);
  // Enforce the cap here as well as in the caller, before opening/rasterizing.
  if (argv.length !== 3 || !Number.isInteger(number) || number < 1 || number > 3)
    return fail("render_failed");
  try {
    const document = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
    if (!document || document.isNil()) return fail("malformed");
    if (document.isLocked) return fail("locked");
    const count = Number(document.pageCount);
    if (!Number.isInteger(count) || count < number) return fail("malformed");
    const page = document.pageAtIndex(number - 1);
    if (!page || page.isNil()) return fail("malformed");
    const bounds = page.boundsForBox(0); // media box, PDF points at 72 dpi
    const width = Math.ceil(Number(bounds.size.width) * 2);
    const height = Math.ceil(Number(bounds.size.height) * 2);
    // Reject giant/nonfinite page geometry BEFORE allocating a 144 dpi bitmap.
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0 ||
        width > 4096 || height > 4096 || width * height > 8000000)
      return fail("oversized");
    const thumbnail = page.thumbnailOfSizeForBox($.NSMakeSize(width, height), 0);
    if (!thumbnail || thumbnail.isNil()) return fail("render_failed");
    const bitmap = $.NSBitmapImageRep.imageRepWithData(thumbnail.TIFFRepresentation);
    if (!bitmap || bitmap.isNil()) return fail("render_failed");
    const png = bitmap.representationUsingTypeProperties($.NSPNGFileType, $({}));
    if (!png || png.isNil() || Number(png.length) > 8 * 1024 * 1024)
      return fail("render_failed");
    if (!png.writeToFileAtomically(argv[2], false)) return fail("render_failed");
    return JSON.stringify({status: "ok", page: number, pages: count});
  } catch (_) {
    // Never include native exception details, filenames or PDF metadata.
    return fail("render_failed");
  }
}
