"use strict";
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const feedback = document.querySelector("#feedback");
let polling = null;
function note(text, failed = false) {
  feedback.textContent = text; feedback.classList.remove("hidden");
  feedback.classList.toggle("danger", failed);
}
async function post(url, body = {}) {
  const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: JSON.stringify(body)});
  if (response.redirected) { location.href = response.url; return {}; }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || "Échec de l’opération");
  return data;
}
function node(tag, text, className) {
  const value = document.createElement(tag); if (text !== undefined) value.textContent = text;
  if (className) value.className = className; return value;
}
document.querySelectorAll("[data-api-usage]").forEach(card => {
  const data = JSON.parse(card.dataset.apiUsage);
  const select = card.querySelector("[data-api-endpoint]");
  const type = card.querySelector("[data-api-type]");
  const group = card.querySelector("[data-api-group]");
  const svg = card.querySelector("[data-api-chart]");
  const graphs = card.querySelector("[data-api-graphs]");
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  card.querySelector("[data-api-timezone]").textContent = `Heures locales · ${zone}`;
  function shape(tag, attributes, text) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function labelTotal(total) {
    return `${total.toLocaleString("fr-FR")} appel${total > 1 ? "s" : ""}`;
  }
  function chart(target, counts, title, compact, max) {
    const width = compact ? 360 : 720;
    const gap = (width - 40) / 24;
    target.setAttribute("viewBox", `0 0 ${width} 160`);
    target.replaceChildren();
    target.setAttribute("aria-label", `${title} : ${labelTotal(counts.reduce((a, b) => a + b, 0))}, par heure. ${zone}.`);
    [0, max].forEach(value => {
      const y = 130 - value / max * 110;
      target.append(shape("line", {x1: 38, x2: width - 2, y1: y, y2: y, class: "api-chart-grid"}));
      target.append(shape("text", {x: 30, y: y + 4, "text-anchor": "end", class: "api-chart-label"}, value.toLocaleString("fr-FR")));
    });
    counts.forEach((value, index) => {
      const date = new Date(data.hours[index] * 1000);
      const hour = date.toLocaleTimeString("fr-FR", {hour: "2-digit", minute: "2-digit"});
      const x = 40 + index * gap;
      const height = value / max * 110;
      const rect = shape("rect", {x, y: 130 - height, width: gap * 0.72, height, rx: 3, class: "api-chart-bar", tabindex: 0});
      const detail = `${date.toLocaleDateString("fr-FR")} ${hour} · ${labelTotal(value)}${index === 23 ? " · heure en cours" : ""}`;
      rect.setAttribute("aria-label", detail);
      rect.append(shape("title", {}, detail));
      target.append(rect);
      if (index % (compact ? 6 : 4) === 0 || index === 23) target.append(shape("text", {x: index === 23 ? width - 2 : x + gap * 0.36, y: 151, "text-anchor": index === 23 ? "end" : "middle", class: "api-chart-label"}, hour));
    });
  }
  function draw() {
    const rows = data.rows.filter(row => (!select.value || row.endpoint === select.value) && (!type.value || row.type === type.value));
    const counts = data.hours.map(() => 0);
    const grouped = new Map();
    rows.forEach(row => {
      counts[row.hour] += row.calls;
      const id = group.value === "project" ? row.project_id : group.value === "key" ? row.key_id : row.endpoint;
      if (!grouped.has(id)) grouped.set(id, {counts: data.hours.map(() => 0), types: new Map()});
      const item = grouped.get(id);
      item.counts[row.hour] += row.calls;
      item.types.set(row.type, (item.types.get(row.type) || 0) + row.calls);
    });
    const total = counts.reduce((sum, value) => sum + value, 0);
    card.querySelector("[data-api-total]").textContent = labelTotal(total);
    card.querySelector("[data-api-empty]").hidden = total !== 0;
    card.querySelector("[data-api-key-note]").hidden = group.value !== "key";
    chart(svg, counts, select.selectedOptions[0].textContent, card.clientWidth < 500, Math.max(1, ...counts));
    graphs.replaceChildren();
    // A shared vertical scale makes the separate API charts comparable.
    const max = Math.max(1, ...Array.from(grouped.values()).flatMap(item => item.counts));
    const items = Array.from(grouped.entries()).sort((a, b) => b[1].counts.reduce((x, y) => x + y, 0) - a[1].counts.reduce((x, y) => x + y, 0));
    items.forEach(([id, item]) => {
      const title = group.value === "project" ? data.projects[id] || "Projet non renseigné" : group.value === "key" ? data.keys[id] || "Clé non renseignée" : id;
      const panel = node("article", undefined, "api-mini");
      const heading = node("div", undefined, "api-mini-heading");
      heading.append(node("h3", title), node("strong", labelTotal(item.counts.reduce((sum, value) => sum + value, 0))));
      panel.append(heading);
      const mini = shape("svg", {"data-api-mini-chart": "", role: "img"});
      chart(mini, item.counts, title, true, max);
      panel.append(mini);
      const breakdown = node("div", undefined, "api-type-breakdown");
      Array.from(item.types.entries()).sort((a, b) => b[1] - a[1]).forEach(([name, amount]) => breakdown.append(node("span", `${name} · ${amount.toLocaleString("fr-FR")}`)));
      panel.append(breakdown);
      graphs.append(panel);
    });
  }
  [select, type, group].forEach(control => control.addEventListener("change", draw));
  let lastWidth = card.clientWidth;
  new ResizeObserver(() => {
    if (lastWidth !== card.clientWidth) { lastWidth = card.clientWidth; draw(); }
  }).observe(card);
  draw();
});
function showSecret(secret) {
  document.querySelector("#secret-value").textContent = secret;
  document.querySelector("#secret-panel").classList.remove("hidden");
  document.querySelector("#secret-panel").scrollIntoView({behavior:"smooth", block:"center"});
}
document.querySelector("#copy-secret").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(document.querySelector("#secret-value").textContent); note("Clé copiée."); }
  catch { note("Sélectionnez le texte de la clé pour la copier."); }
});
document.querySelector("#dismiss-secret").addEventListener("click", () => {
  document.querySelector("#secret-value").textContent = ""; location.reload();
});
document.querySelectorAll('form[data-key-settings]').forEach(form => {
  const toggle = form.querySelector("[data-key-expiration]");
  const date = form.querySelector("[data-key-expiration-date]");
  const help = form.querySelector("[data-key-expiration-help]");
  const project = form.querySelector('[data-key-project]');
  if (date.dataset.initialTimestamp) {
    const initial = new Date(Number(date.dataset.initialTimestamp) * 1000);
    const pad = value => String(value).padStart(2, "0");
    date.type = "datetime-local";
    date.value = `${initial.getFullYear()}-${pad(initial.getMonth()+1)}-${pad(initial.getDate())}T${pad(initial.getHours())}:${pad(initial.getMinutes())}:${pad(initial.getSeconds())}`;
    date.dataset.initialLocalValue = date.value;
    date.step = "1";
  }
  function updateExpiration() {
    date.disabled = !toggle.checked;
    date.required = toggle.checked;
    if (toggle.checked) {
      date.type = "datetime-local";
      date.removeAttribute("placeholder");
    } else {
      date.value = "";
      date.type = "text";
      date.placeholder = "Sans expiration";
    }
    help.textContent = toggle.checked
      ? "Choisissez une date future, dans le fuseau horaire de ce navigateur. La clé sera automatiquement refusée à partir de cette date."
      : "Sans expiration : le champ est vide et désactivé. La clé reste valide jusqu’à sa révocation ou sa rotation.";
  }
  function updateRateHelp() {
    const limit = project.selectedOptions[0]?.dataset.rateLimit;
    form.querySelector("[data-key-project-rate-help]").textContent = limit
      ? `Plafond de ce projet : ${limit} requêtes par minute et par clé. La limite effective est la plus petite entre ce plafond et la valeur saisie ci-dessus.`
      : "Créez un projet pour choisir le plafond de cette clé.";
  }
  toggle.addEventListener("change", updateExpiration);
  project.addEventListener("change", updateRateHelp);
  updateExpiration(); updateRateHelp();
});
document.querySelectorAll("[data-policy-toggle]").forEach(toggle => {
  const config = toggle.closest("form").querySelector('[name="config"]');
  config.addEventListener("input", () => {
    try { toggle.checked = JSON.parse(config.value)[toggle.dataset.policyToggle] === true; }
    catch { /* Keep the current selection while JSON is being edited. */ }
  });
  toggle.addEventListener("change", () => {
    try {
      const policy = JSON.parse(config.value);
      policy[toggle.dataset.policyToggle] = toggle.checked;
      config.value = JSON.stringify(policy, null, 2);
    } catch { note("Corrigez la configuration JSON avant de modifier cette option.", true); }
  });
});
function displayJob(data, project, jobId) {
  document.querySelector("#job-panel").classList.remove("hidden");
  document.querySelector("#job-status").textContent = data.status;
  const output = document.querySelector("#job-output"); output.replaceChildren();
  if (data.error) output.append(node("p", data.error.code + " · " + data.error.message, "notice danger"));
  if (data.status === "waiting_for_human") {
    output.append(node("p", "Intervenez manuellement dans le navigateur du Mac, puis confirmez pour reprendre.", "notice warning"));
    for (const [action, label] of [["resume", "J’ai terminé — reprendre"], ["cancel", "Annuler"]]) {
      const button = node("button", label); button.addEventListener("click", async () => {
        try { await post(`/admin/projects/${project}/jobs/${jobId}/${action}`); watchJob(project, jobId); }
        catch (e) { note(e.message, true); }
      }); output.append(button);
    }
  }
  const result = data.result;
  if (result?.results) for (const entry of result.results) {
    const section = node("article", undefined, "result");
    section.append(node("h3", entry.rank + ". " + entry.title));
    section.append(node("span", entry.url, "result-url"), node("p", entry.snippet));
    section.append(node("p", entry.source_engines.join(" · ") + " · Type de résultat : " + entry.result_type, "footnote"));
    const button = node("button", "Ouvrir dans ce profil");
    button.addEventListener("click", async () => {
      try { const value = await post(`/admin/projects/${project}/tabs`, {url: entry.url}); watchJob(project, value.job_id); }
      catch (e) { note(e.message, true); }
    }); section.append(button); output.append(section);
  }
  const capture = result?.capture || (result?.media_type === "image/png" ? result : null);
  if (capture) {
    const image = node("img"); image.alt = "Capture protégée du navigateur";
    image.src = `/admin/projects/${project}/artifacts/${capture.artifact_id}`; output.append(image);
  } else if (result && !result.results) output.append(node("pre", JSON.stringify(result, null, 2)));
}
document.querySelectorAll('form[data-api-project="search"]').forEach(form => {
  const engine = form.querySelector('[name="engine"]');
  function updateFilters() {
    const enabled = engine.value === "duckduckgo";
    form.querySelectorAll('[data-ddg-filter]').forEach(control => control.disabled = !enabled);
  }
  engine.addEventListener("change", updateFilters);
  updateFilters();
});
async function watchJob(project, jobId) {
  clearTimeout(polling);
  try {
    const response = await fetch(`/admin/projects/${project}/jobs/${jobId}`);
    const data = await response.json(); if (!response.ok) throw new Error(data.error?.message || "Job inaccessible");
    displayJob(data, project, jobId);
    if (["queued", "running"].includes(data.status)) polling = setTimeout(() => watchJob(project, jobId), 1000);
  } catch (e) { note(e.message, true); }
}
document.querySelectorAll("form[data-api],form[data-api-project]").forEach(form => form.addEventListener("submit", async event => {
  event.preventDefault(); const button = form.querySelector('button[type="submit"],button'); button.disabled = true;
  try {
    const fields = new FormData(form); const body = form.hasAttribute("data-json") ? JSON.parse(fields.get("config")) : Object.fromEntries(fields);
    let project = fields.get("project"); let url = form.dataset.api;
    if (form.dataset.apiProject) { url = `/admin/projects/${project}/${form.dataset.apiProject}`; delete body.project; }
    if (!form.hasAttribute("data-json")) {
      if (form.dataset.apiProject === "search" && body.region === "") delete body.region;
      form.querySelectorAll("[data-number]").forEach(el => body[el.name] = el.hasAttribute("data-nullable") && el.value === "" ? null : Number(el.value));
      form.querySelectorAll("[data-boolean]").forEach(el => body[el.name] = el.checked);
      form.querySelectorAll("[data-timestamp]").forEach(el => {
        body[el.name] = null;
        if (!el.disabled && el.value) body[el.name] = el.dataset.initialTimestamp && el.value === el.dataset.initialLocalValue
          ? Number(el.dataset.initialTimestamp) : new Date(el.value).getTime()/1000;
      });
      if (form.querySelector('[name="scopes"]')) {
        body.scopes = fields.getAll("scopes");
        if (!body.scopes.length) throw new Error("Choisissez au moins une autorisation. Pour bloquer tous les accès, révoquez la clé.");
      }
    }
    const result = await post(url, body);
    if (result.secret) showSecret(result.secret);
    else if (result.job_id) watchJob(project, result.job_id);
    else { note("Opération effectuée."); if (result.redirect_url === "/admin/keys") location.href = result.redirect_url; else location.reload(); }
  } catch (e) { note(e.message, true); }
  finally { button.disabled = false; }
}));
document.querySelectorAll("[data-post]").forEach(button => button.addEventListener("click", async () => {
  if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
  button.disabled = true;
  try {
    const result = await post(button.dataset.post);
    if (result.secret) showSecret(result.secret);
    else if (result.job_id) watchJob(button.dataset.post.split("/")[3], result.job_id);
    else location.reload();
  } catch (e) { note(e.message, true); }
  finally { button.disabled = false; }
}));
document.querySelectorAll("[data-reset]").forEach(button => button.addEventListener("click", async () => {
  const slug = button.dataset.reset;
  if (prompt(`Première confirmation : saisissez ${slug} pour effacer son profil.`) !== slug) return;
  if (!confirm("Seconde confirmation : cookies, sessions, localStorage et cache seront définitivement effacés. Continuer ?")) return;
  try {
    const intent = await post(`/admin/projects/${slug}/reset-intent`);
    await post(`/admin/projects/${slug}/reset`, {confirmation_slug: slug, confirm_loss: true, confirmation_token: intent.confirmation_token});
    location.reload();
  } catch (e) { note(e.message, true); }
}));
document.querySelectorAll("[data-job]").forEach(button => button.addEventListener("click", () => watchJob(button.dataset.project, button.dataset.job)));

document.querySelectorAll("[data-audit-scroll]").forEach(scroller => {
  const controls = scroller.previousElementSibling;
  const range = controls.querySelector("[data-audit-scroll-range]");
  const left = controls.querySelector("[data-audit-scroll-left]");
  const right = controls.querySelector("[data-audit-scroll-right]");
  function syncScroll() {
    const maximum = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
    range.max = String(maximum);
    range.value = String(scroller.scrollLeft);
    range.disabled = maximum <= 1;
    left.disabled = scroller.scrollLeft <= 1;
    right.disabled = scroller.scrollLeft >= maximum - 1;
  }
  range.addEventListener("input", () => {
    scroller.scrollLeft = Number(range.value);
    syncScroll();
  });
  left.addEventListener("click", () => {
    scroller.scrollLeft -= scroller.clientWidth * 0.75;
    syncScroll();
  });
  right.addEventListener("click", () => {
    scroller.scrollLeft += scroller.clientWidth * 0.75;
    syncScroll();
  });
  scroller.addEventListener("scroll", syncScroll, {passive: true});
  const observer = new ResizeObserver(syncScroll);
  observer.observe(scroller);
  observer.observe(scroller.querySelector("table"));
  syncScroll();
});

document.querySelectorAll("[data-audit-filters]").forEach(form => {
  const dates = [...form.querySelectorAll("[data-audit-date]")];
  function localDateValue(date) {
    const pad = value => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
  dates.forEach(input => {
    if (input.dataset.initialDate) input.value = localDateValue(new Date(input.dataset.initialDate));
  });
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  form.querySelector("[data-audit-timezone]").textContent = `Dates et heures locales · ${zone}`;
  document.querySelectorAll("[data-audit-epoch]").forEach(cell => {
    const date = new Date(Number(cell.dataset.auditEpoch) * 1000);
    cell.textContent = localDateValue(date).slice(0, 16).replace("T", " ");
    cell.title = `${date.toISOString()} · ${zone}`;
  });
  form.querySelectorAll("[data-audit-job-at]").forEach(option => {
    if (!option.dataset.auditJobAt) return;
    const date = new Date(Number(option.dataset.auditJobAt) * 1000);
    const localTime = localDateValue(date).slice(0, 16).replace("T", " ");
    option.textContent = `${option.dataset.auditJobLabel} · ${localTime}`;
  });
  function applyFilters(periodDates) {
    const params = new URLSearchParams(new FormData(form));
    dates.forEach(input => {
      const date = periodDates?.[input.name] || (input.value ? new Date(input.value) : null);
      if (date) params.set(input.name, date.toISOString());
      else params.delete(input.name);
    });
    for (const [name, value] of [...params]) if (value === "") params.delete(name);
    const target = new URL(form.getAttribute("action") || location.href, location.href);
    target.search = params.toString();
    location.assign(target.href);
  }
  form.addEventListener("submit", event => {
    event.preventDefault();
    applyFilters();
  });
  form.querySelectorAll("[data-audit-period]").forEach(button => button.addEventListener("click", () => {
    const until = new Date();
    let since;
    if (button.dataset.auditPeriod === "today") {
      since = new Date(until);
      since.setHours(0, 0, 0, 0);
    } else {
      const minutes = button.dataset.auditPeriod === "10m" ? 10 : 60;
      since = new Date(until.getTime() - minutes * 60 * 1000);
    }
    applyFilters({since, until});
  }));
});
