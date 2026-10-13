(function (options) {
  const {kind, max_bytes} = options;
  const encoder = new TextEncoder();
  const well = value => new TextDecoder().decode(encoder.encode(value));
  const clip = (value, chars) => well(String(value ?? '').slice(0, chars));
  const respond = value => {
    const output = JSON.stringify({value});
    const limit = kind === 'text' || kind === 'html' ? max_bytes * 6 + 128 : max_bytes;
    if (output.length > limit || encoder.encode(output).length > limit)
      return JSON.stringify({too_large: true});
    return output;
  };
  const title = () => clip(document.title, 512);
  if (kind === 'title') return respond({title: title(), title_truncated: document.title.length > 512});
  if (kind === 'challenge') {
    // A form widget or invisible badge does not block reading the main document.
    // Preserve explicit challenges and visible CAPTCHA frames covering the viewport.
    const widgets = document.querySelectorAll('iframe[src*="recaptcha"],iframe[src*="hcaptcha"]');
    let blockingFrame = !!document.querySelector('[data-pq-challenge="true"]');
    const viewportArea = Math.max(1, innerWidth * innerHeight);
    for (let i = 0; i < Math.min(widgets.length, 32); i++) {
      const element = widgets[i];
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const width = Math.max(0, Math.min(rect.right, innerWidth) - Math.max(0, rect.left));
      const height = Math.max(0, Math.min(rect.bottom, innerHeight) - Math.max(0, rect.top));
      if (style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0
          && width * height >= viewportArea * 0.5) blockingFrame = true;
    }
    return respond({title: title(), text: clip(document.body?.innerText, 20000),
      frame: blockingFrame, captcha_widget: widgets.length > 0});
  }
  if (kind === 'text' || kind === 'html') {
    let value;
    if (kind === 'text') value = document.body?.innerText || '';
    else {
      const type = document.doctype;
      let prefix = '';
      if (type) {
        prefix = '<!DOCTYPE ' + type.name;
        if (type.publicId) prefix += ' PUBLIC "' + type.publicId + '"';
        else if (type.systemId) prefix += ' SYSTEM';
        if (type.systemId) prefix += ' "' + type.systemId + '"';
        prefix += '>';
      }
      value = prefix + (document.documentElement?.outerHTML || '');
    }
    if (value.length > max_bytes || encoder.encode(value).length > max_bytes)
      return JSON.stringify({too_large: true});
    return respond(well(value));
  }
  if (kind === 'links') return respond(Array.from(document.querySelectorAll('a[href]')).slice(0,1000)
    .map(el => ({text: clip(el.innerText,500), url: clip(el.href,2048)})));
  if (kind === 'metadata') return respond({title: title(), url: clip(location.href,4096),
    meta: Array.from(document.querySelectorAll('meta[name],meta[property]')).slice(0,100)
      .map(el => ({name: clip(el.name || el.getAttribute('property'),256), content: clip(el.content,2000)}))});
  throw new Error('Unknown fixed read');
})
