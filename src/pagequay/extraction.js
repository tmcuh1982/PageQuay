/* Fixed, read-only snapshot. No caller-supplied code, clicks, scrolling or network calls. */
({ include_dom, text_budget }) => {
  const reasons = new Set();
  const limits = { nodes: 8000, depth: 32, wrapper_credit: 3, physical_depth: 35, blocks: 400, links: 300, images: 100,
    tables: 20, rows: 50, cells: 30, controls: 100, forms: 30, options: 300, json_ld: 10 };
  let characters = 0, nodes = 0, visited = 0, shadowRoots = 0;
  const seen = new WeakSet();
  const cut = (reason) => reasons.add(reason);
  const clip = (value, max = 2000) => {
    const raw = String(value ?? '');
    const available = Math.max(0, text_budget - characters);
    const length = Math.min(max, available);
    if (raw.length > length) cut(available < max ? 'text_budget' : 'string_length');
    const result = new TextDecoder().decode(new TextEncoder().encode(raw.slice(0, length)));
    characters += result.length;
    return result;
  };
  // Reserve identity before metadata and DOM consume the shared budget.
  const identity = { url: clip(location.href, 4096), title: clip(document.title, 500) };
  const safeUrl = (value, image = false) => {
    if (!value) return null;
    try {
      if (String(value).length > 2048) cut('url_length');
      const url = new URL(String(value).slice(0, 2048), document.baseURI);
      if (!(image ? ['http:', 'https:'] : ['http:', 'https:', 'mailto:', 'tel:']).includes(url.protocol)) return null;
      url.username = ''; url.password = '';
      return clip(url.href, 2048);
    } catch { return null; }
  };
  const allowed = ['id', 'class', 'role', 'aria-label', 'aria-labelledby', 'aria-describedby',
    'aria-level', 'aria-expanded', 'aria-checked', 'aria-disabled', 'name', 'type',
    'alt', 'title', 'for', 'form', 'method', 'colspan', 'rowspan'];
  const omitted = new Set(['script', 'style', 'noscript', 'template', 'head']);
  const attributes = (el) => {
    const result = {};
    for (const name of allowed) {
      if (el.hasAttribute(name)) result[name] = clip(el.getAttribute(name), 256);
    }
    for (const name of ['href', 'src', 'action']) {
      const value = safeUrl(el.getAttribute(name), name === 'src');
      if (value) result[name] = value;
    }
    if (el.tagName === 'IMG') {
      const src = safeUrl(el.currentSrc || el.getAttribute('src'), true);
      if (src) result.src = src;
    }
    for (const name of ['disabled', 'required', 'readonly']) {
      if (el.hasAttribute(name)) result[name] = true;
    }
    if (['input', 'button'].includes(el.localName)) result.type = clip(el.type, 40);
    if (el.matches(':disabled')) result.disabled = true;
    return result;
  };
  const provenanceOf = (node) => {
    const parts = [];
    let current = node, scanned = 0;
    while (current && current.nodeType !== Node.DOCUMENT_NODE) {
      if (parts.length >= 32) return { xpath: null, xpath_reason: 'depth_limit' };
      if (current.nodeType === Node.DOCUMENT_FRAGMENT_NODE)
        return { xpath: null, xpath_reason: 'shadow_root' };
      const text = current.nodeType === Node.TEXT_NODE;
      let position = 1;
      for (let sibling = current.previousSibling; sibling; sibling = sibling.previousSibling) {
        if (++scanned > 2000) return { xpath: null, xpath_reason: 'sibling_limit' };
        if (sibling.nodeType === (text ? Node.TEXT_NODE : Node.ELEMENT_NODE)) position++;
      }
      parts.push(text ? `text()[${position}]` : `*[${position}]`);
      current = current.parentNode;
    }
    return current ? { xpath: '/' + parts.reverse().join('/'), xpath_reason: null } :
      { xpath: null, xpath_reason: 'not_in_document' };
  };
  // Discount at most three layout envelopes per path, never semantic nodes or
  // shadow/projection boundaries. Keep the envelopes in the returned tree.
  const neutralEnvelope = (node) => {
    if (node.nodeType !== Node.ELEMENT_NODE || !['div', 'span', 'picture'].includes(node.localName) ||
      node.shadowRoot || node.assignedSlot || node.isContentEditable || node.attributes.length > 32) return false;
    for (const attr of node.attributes) {
      if (!['id', 'class', 'style'].includes(attr.name) && !attr.name.startsWith('data-')) return false;
    }
    return true;
  };
  const build = (node, depth = 0, wrapperCredit = 0) => {
    if (visited >= limits.nodes) { cut('nodes'); return null; }
    visited++;
    if (depth > limits.physical_depth) { cut('depth'); return null; }
    if (wrapperCredit < limits.wrapper_credit && neutralEnvelope(node)) wrapperCredit++;
    if (depth - wrapperCredit > limits.depth) { cut('depth'); return null; }
    if (seen.has(node)) return null;
    seen.add(node);
    if (node.nodeType === Node.TEXT_NODE) {
      if (!node.nodeValue.slice(0, 4096).trim()) {
        if (node.nodeValue.length > 4096) cut('string_length');
        return null;
      }
      nodes++;
      return { node_id: `n${nodes}`, provenance: provenanceOf(node), tag: '#text', text: clip(node.nodeValue, 4096) };
    }
    if (![Node.ELEMENT_NODE, Node.DOCUMENT_FRAGMENT_NODE].includes(node.nodeType)) return null;
    const tag = node.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? '#shadow-root' : node.localName;
    if (omitted.has(tag)) return null;
    if (node.nodeType === Node.ELEMENT_NODE) {
      const style = getComputedStyle(node);
      if (node.hidden || node.getAttribute('aria-hidden') === 'true' || style.display === 'none' ||
        style.visibility === 'hidden' || style.contentVisibility === 'hidden' ||
        (tag === 'input' && node.type === 'hidden')) return null;
    }
    nodes++;
    const result = { node_id: `n${nodes}`, provenance: provenanceOf(node), tag, attributes: tag === '#shadow-root' ? {} : attributes(node), children: [] };
    // Never serialize input/textarea values, including initial textarea text nodes.
    if (tag === 'input' || tag === 'textarea') return result;
    let children = node.childNodes;
    if (node.shadowRoot) {
      shadowRoots++;
      children = [node.shadowRoot];
    } else if (tag === 'slot') {
      const assigned = node.assignedNodes({ flatten: true });
      if (assigned.length) children = assigned;
    }
    for (const child of children) {
      if (visited >= limits.nodes) { cut('nodes'); break; }
      const value = build(child, depth + 1, wrapperCredit);
      if (value) result.children.push(value);
    }
    return result;
  };
  const walk = (node, visit, skip = () => false) => {
    if (!node || skip(node)) return;
    visit(node);
    for (const child of node.children || []) walk(child, visit, skip);
  };
  const textOf = (node, skip = () => false, preserve = false) => {
    let result = '';
    walk(node, (item) => {
      if (item.tag === '#text') result += item.text;
      else if (['div', 'p', 'li', 'label', 'br', 'tr'].includes(item.tag)) result += ' ';
    }, skip);
    if (result.length > 4096) cut('block_text');
    result = result.slice(0, 4096);
    return preserve ? result.trim() : result.replace(/\s+/g, ' ').trim();
  };
  const append = (array, value, name, max) => {
    if (array.length < max) array.push(value);
    else cut(name);
  };
  const metadata = { language: clip(document.documentElement.lang, 40), meta: [], json_ld: [] };
  for (const el of document.querySelectorAll('meta[name],meta[property]')) {
    if (metadata.meta.length >= 100) { cut('metadata'); break; }
    metadata.meta.push({ name: clip(el.name || el.getAttribute('property'), 256), content: clip(el.content, 1000) });
  }
  metadata.description = metadata.meta.find((m) => m.name === 'description')?.content || null;
  metadata.canonical = safeUrl(document.querySelector('link[rel="canonical"]')?.href);
  let jsonNodes = 0;
  const boundedJson = (value, depth = 0) => {
    if (++jsonNodes > 1000 || depth > 20) { cut('json_ld_nodes'); return null; }
    if (typeof value === 'string') return clip(value, 2000);
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (Array.isArray(value)) {
      if (value.length > 100) cut('json_ld_items');
      return value.slice(0, 100).map((item) => boundedJson(item, depth + 1));
    }
    if (value && typeof value === 'object') {
      const result = Object.create(null);
      let count = 0;
      for (const [key, item] of Object.entries(value)) {
        if (count++ >= 100) { cut('json_ld_keys'); break; }
        result[clip(key, 256)] = boundedJson(item, depth + 1);
      }
      return result;
    }
    return value;
  };
  let jsonScripts = 0;
  for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
    if (jsonScripts++ >= limits.json_ld) { cut('json_ld'); break; }
    if (el.textContent.length > 20000) { cut('json_ld_length'); continue; }
    try { metadata.json_ld.push(boundedJson(JSON.parse(el.textContent))); }
    catch { cut('invalid_json_ld'); }
  }
  const tree = document.body ? build(document.body) : null;
  const links = [], images = [], tables = [], controls = [], forms = [], visuals = [], landmarks = [];
  const index = new Map(), htmlIds = new Map(), labels = new Map();
  const role = (node) => node.attributes?.role || '';
  const isTable = (node) => node.tag === 'table' || ['table', 'grid', 'treegrid'].includes(role(node));
  const isList = (node) => ['ul', 'ol'].includes(node.tag) || role(node) === 'list';
  walk(tree, (node) => {
    index.set(node.node_id, node);
    if (node.attributes?.id) htmlIds.set(node.attributes.id, node);
    if (node.tag === 'label' && node.attributes?.for) labels.set(node.attributes.for, node);
  });
  const labelOf = (node) => {
    const attrs = node.attributes || {};
    if (attrs['aria-label']) return attrs['aria-label'];
    const labelled = (attrs['aria-labelledby'] || '').split(/\s+/).map((id) => htmlIds.get(id)).filter(Boolean);
    if (labelled.length) return labelled.map((item) => textOf(item)).join(' ').slice(0, 1000);
    if (labels.has(attrs.id)) return textOf(labels.get(attrs.id));
    return attrs.title || '';
  };
  const tableOf = (node) => {
    const rows = [];
    walk(node, (row) => {
      if (row.tag !== 'tr' && role(row) !== 'row') return;
      const cells = [];
      walk(row, (cell) => {
        if (!['td', 'th'].includes(cell.tag) && !['cell', 'gridcell', 'rowheader', 'columnheader'].includes(role(cell))) return;
        append(cells, {
          node_id: cell.node_id, text: textOf(cell), header: cell.tag === 'th' || ['rowheader', 'columnheader'].includes(role(cell)),
          colspan: Math.min(1000, Math.max(1, Number(cell.attributes?.colspan) || 1)),
          rowspan: Math.min(1000, Math.max(1, Number(cell.attributes?.rowspan) || 1))
        }, 'table_cells', limits.cells);
      }, (item) => item !== row && (isTable(item) || item.tag === 'tr' || role(item) === 'row'));
      append(rows, cells, 'table_rows', limits.rows);
    }, (item) => item !== node && isTable(item));
    let caption = '';
    walk(node, (item) => { if (item.tag === 'caption') caption = textOf(item); }, (item) => item !== node && isTable(item));
    return { node_id: node.node_id, caption: caption || labelOf(node), kind: role(node) || 'table', rows };
  };
  const collect = (node, form = null, wrappingLabel = '') => {
    if (!node) return;
    const attrs = node.attributes || {};
    if (node.tag === 'label') wrappingLabel = textOf(node);
    if (node.tag === 'form' || role(node) === 'form') {
      form = { node_id: node.node_id, action: attrs.action || null, method: (attrs.method || 'get').toLowerCase(), label: labelOf(node), control_ids: [] };
      append(forms, form, 'forms', limits.forms);
    }
    if (node.tag === 'a' && attrs.href) append(links, { node_id: node.node_id, text: textOf(node) || labelOf(node), url: attrs.href }, 'links', limits.links);
    if (node.tag === 'img') append(images, { node_id: node.node_id, url: attrs.src || null, alt: attrs.alt || '' }, 'images', limits.images);
    if (isTable(node)) append(tables, tableOf(node), 'tables', limits.tables);
    if (['input', 'select', 'textarea', 'button'].includes(node.tag) || ['button', 'textbox', 'checkbox', 'combobox', 'switch'].includes(role(node))) {
      const control = {
        node_id: node.node_id, tag: node.tag, type: attrs.type || role(node) || node.tag,
        name: attrs.name || '', label: labelOf(node) || wrappingLabel || (node.tag === 'button' ? textOf(node) : ''),
        required: Boolean(attrs.required), disabled: Boolean(attrs.disabled) || attrs['aria-disabled'] === 'true',
        value_omitted: true, form_id: (attrs.form ? htmlIds.get(attrs.form)?.node_id : form?.node_id) || null
      };
      if (node.tag === 'select') {
        control.options = [];
        walk(node, (item) => { if (item.tag === 'option') append(control.options, textOf(item), 'options', limits.options); });
      }
      append(controls, control, 'controls', limits.controls);
      if (form && controls.includes(control)) form.control_ids.push(node.node_id);
    }
    if (['main', 'article', 'nav', 'aside', 'header', 'footer'].includes(node.tag) || ['main', 'region', 'navigation'].includes(role(node))) {
      append(landmarks, { node_id: node.node_id, tag: node.tag, role: role(node), label: labelOf(node) }, 'landmarks', 100);
    }
    if (node.tag === 'canvas' || node.tag === 'svg') {
      append(visuals, { node_id: node.node_id, type: node.tag, label: labelOf(node), requires_screenshot: true }, 'visuals', 50);
    }
    for (const child of node.children || []) collect(child, form, wrappingLabel);
  };
  collect(tree);
  for (const form of forms) form.control_ids = controls.filter((control) => control.form_id === form.node_id).map((control) => control.node_id);
  const listOf = (node) => {
    const items = [];
    const visit = (item) => {
      if (item.tag === 'li' || role(item) === 'listitem') {
        const children = [];
        walk(item, (child) => { if (isList(child)) children.push(listOf(child)); }, (child) => child !== item && (child.tag === 'li' || role(child) === 'listitem'));
        append(items, { node_id: item.node_id, text: textOf(item, (child) => child !== item && isList(child)), children }, 'list_items', 100);
        return;
      }
      for (const child of item.children || []) visit(child);
    };
    for (const child of node.children || []) visit(child);
    return { node_id: node.node_id, ordered: node.tag === 'ol', items };
  };
  // Prefer the visible main region for reading; global links/controls remain available.
  const main = [...index.values()].find((node) => node.tag === 'main' || role(node) === 'main') || tree;
  const blocks = [];
  let pending = '', pendingId = null;
  const emit = (block) => append(blocks, { ...block, provenance: index.get(block.node_id)?.provenance || { xpath: null, xpath_reason: 'node_unavailable' } }, 'blocks', limits.blocks);
  const flush = () => {
    const text = pending.replace(/\s+/g, ' ').trim();
    if (text) emit({ type: 'paragraph', node_id: pendingId, text: text.slice(0, 4096) });
    if (text.length > 4096) cut('block_text');
    pending = ''; pendingId = null;
  };
  const render = (node) => {
    if (!node) return;
    if (node.tag === '#text') { pending += node.text; pendingId ||= node.node_id; return; }
    const heading = /^h[1-6]$/.test(node.tag) || role(node) === 'heading';
    if (heading || ['p', 'pre', 'blockquote'].includes(node.tag) || isList(node) || isTable(node) || node.tag === 'iframe') {
      flush();
      if (heading) {
        const level = Number(node.attributes['aria-level'] || node.tag.slice(1));
        const valid = Number.isSafeInteger(level) && level > 0;
        if (!valid) cut('invalid_heading_level');
        emit({ type: 'heading', node_id: node.node_id, level: valid ? level : 2, text: textOf(node) });
      }
      else if (isList(node)) emit({ type: 'list', ...listOf(node) });
      else if (isTable(node)) emit({ type: 'table', node_id: node.node_id, table_id: node.node_id });
      else if (node.tag === 'iframe') emit({ type: 'frame', node_id: node.node_id, url: node.attributes.src || null, title: node.attributes.title || '' });
      else emit({ type: node.tag === 'pre' ? 'code' : node.tag === 'blockquote' ? 'quote' : 'paragraph', node_id: node.node_id, text: textOf(node, () => false, node.tag === 'pre') });
      return;
    }
    const boundary = ['div', 'section', 'article', 'nav', 'header', 'footer', 'form', 'li', '#shadow-root'].includes(node.tag);
    if (boundary) flush();
    for (const child of node.children || []) render(child);
    if (boundary) flush();
  };
  render(main); flush();
  const result = {
    title: identity.title, url: identity.url, metadata,
    content_root: main?.node_id || null, blocks, links, images, tables, controls, forms, visuals, landmarks,
    stats: { nodes_visited: visited, nodes_included: nodes, open_shadow_roots: shadowRoots, characters },
    truncated: reasons.size > 0, truncation_reasons: [...reasons]
  };
  if (include_dom) result.dom = { root: tree, filtered: true, excluded: ['hidden_elements', 'scripts', 'styles', 'form_values'] };
  return result;
}
