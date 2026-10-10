// Read the owner-selected Safari tab only. No navigation, clicks, form fills,
// or shell. Invoked as: osascript -l JavaScript safari_tab.js url|text
function run(argv) {
  const mode = argv[0];
  if (mode !== "url" && mode !== "text") throw new Error("unsupported");
  const safari = Application("Safari");
  if (!safari.running()) throw new Error("Safari is not running");
  const window = safari.windows[0];
  if (!window || window.id() === undefined) throw new Error("No Safari window");
  const tab = window.currentTab();
  if (!tab) throw new Error("No selected Safari tab");
  const url = String(tab.url() || "");
  const title = String(tab.name() || "");
  if (mode === "url") return JSON.stringify({url: url, title: title});
  const extract =
    "(function(){" +
    "function skip(node){" +
    "if(!node||!node.nodeName)return true;" +
    "var tag=String(node.nodeName).toUpperCase();" +
    "if(/^(INPUT|TEXTAREA|SELECT|OPTION|SCRIPT|STYLE|NOSCRIPT|BUTTON)$/.test(tag))return true;" +
    "if(node.isContentEditable)return true;" +
    "return false;}" +
    "function collect(node,parts){" +
    "if(!node||skip(node))return;" +
    "if(node.nodeType===3){var t=node.nodeValue;if(t&&t.trim())parts.push(t);return;}" +
    "if(node.nodeType!==1)return;" +
    "var kids=node.childNodes||[];" +
    "for(var i=0;i<kids.length;i++)collect(kids[i],parts);}" +
    "var parts=[];collect(document.body,parts);" +
    "return parts.join(' ').replace(/\\s+/g,' ').trim();" +
    "})()";
  const text = safari.doJavaScript(extract, {in: tab});
  return JSON.stringify({url: url, title: title, text: text == null ? "" : String(text)});
}
