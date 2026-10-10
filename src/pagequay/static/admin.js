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
      form.querySelectorAll("[data-number]").forEach(el => body[el.name] = Number(el.value));
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
