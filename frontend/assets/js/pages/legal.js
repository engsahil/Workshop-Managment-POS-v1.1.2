// Legal Documents — Privacy Policy & Terms and Conditions (editable by Administrator).
import { api, auth } from "../core/api.js";
import { esc, formData, openModal, toast } from "../core/ui.js";

export async function renderLegalPublic(key = "privacy_policy") {
  const cleanKey = key === "terms_conditions" ? "terms_conditions" : "privacy_policy";
  try {
    const doc = await api.get(`/api/settings/legal/${cleanKey}`);
    openModal({
      title: doc.title || (cleanKey === "terms_conditions" ? "Terms & Conditions" : "Privacy Policy"),
      size: "lg",
      body: `
        <div style="white-space:pre-wrap;line-height:1.65;font-size:13.5px;max-height:65vh;overflow-y:auto">${esc(doc.content)}</div>
        <div class="modal-foot">
          <button type="button" class="btn btn-primary" data-close>Close</button>
        </div>`,
    });
  } catch (err) {
    toast(err.message || "Unable to load legal document", "err");
  }
}

export async function renderLegal(root, defaultKey = "privacy_policy") {
  const isAdmin = auth.hasRole("admin");
  const initialKey = defaultKey === "terms_conditions" ? "terms_conditions" : "privacy_policy";
  root.innerHTML = `
    <div class="tabs">
      <div class="tab ${initialKey === "privacy_policy" ? "active" : ""}" data-k="privacy_policy">Privacy Policy</div>
      <div class="tab ${initialKey === "terms_conditions" ? "active" : ""}" data-k="terms_conditions">Terms &amp; Conditions</div>
    </div>
    <div id="leg-body"></div>
  `;
  let curKey = initialKey;

  async function load() {
    const box = root.querySelector("#leg-body");
    try {
      const doc = await api.get(`/api/settings/legal/${curKey}`);
      box.innerHTML = `
        <div class="card">
          <div class="card-head">
            <div>
              <h3 class="card-title">${esc(doc.title)}</h3>
              <div class="card-sub">${doc.is_default ? "Default template — adapt to your business requirements." : "Customized by workshop administrator"}</div>
            </div>
            ${isAdmin ? `<button class="btn btn-ghost btn-sm" id="leg-edit">Edit Document</button>` : ""}
          </div>
          <div style="white-space:pre-wrap;line-height:1.65;font-size:13.5px">${esc(doc.content)}</div>
        </div>`;
      const eb = box.querySelector("#leg-edit");
      if (eb) {
        eb.onclick = () => {
          const m = openModal({
            title: `Edit ${doc.title}`,
            size: "lg",
            body: `
              <form id="leg-f">
                <label><span>Title *</span><input name="title" required value="${esc(doc.title)}" /></label>
                <label><span>Content *</span><textarea name="content" style="min-height:280px" required>${esc(doc.content)}</textarea></label>
                <div class="modal-foot">
                  <button type="button" class="btn btn-ghost" data-close>Cancel</button>
                  <button type="submit" class="btn btn-primary">Save Document</button>
                </div>
              </form>`,
          });
          m.root.querySelector("#leg-f").onsubmit = async (e) => {
            e.preventDefault();
            await api.put(`/api/settings/legal/${curKey}`, formData(e.target));
            toast("Legal document updated");
            m.close();
            load();
          };
        };
      }
    } catch (err) {
      box.innerHTML = `
        <div class="card">
          <div class="form-error" style="margin-bottom:10px">${esc(err.message || "Failed to load legal document")}</div>
          <button class="btn btn-ghost btn-sm" id="leg-retry">Retry</button>
        </div>`;
      box.querySelector("#leg-retry").onclick = () => load();
    }
  }

  root.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      curKey = t.dataset.k;
      load();
    };
  });

  await load();
}

export default {
  route: "privacy",
  title: "Privacy Policy",
  load: async () => (root) => renderLegal(root, "privacy_policy"),
};

export const termsPage = {
  route: "terms",
  title: "Terms & Conditions",
  load: async () => (root) => renderLegal(root, "terms_conditions"),
};
