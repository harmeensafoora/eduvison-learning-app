(() => {
  const toastRootId = "toast-root";

  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  function $all(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatInline(text) {
    const escaped = escapeHtml(text);
    return escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function renderMarkdown(md) {
    const src = String(md || "").replace(/\r\n/g, "\n");
    const lines = src.split("\n");
    let html = "";
    let inList = false;

    for (const raw of lines) {
      const line = raw.trimEnd();
      if (!line.trim()) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        continue;
      }
      if (line.startsWith("### ")) {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += `<h3 style="margin:.9rem 0 .35rem; letter-spacing:-0.02em;">${formatInline(line.slice(4).trim())}</h3>`;
        continue;
      }
      if (line.startsWith("- ") || line.startsWith("* ")) {
        if (!inList) {
          html += '<ul style="margin:.45rem 0 .75rem; padding-left:1.25rem; display:grid; gap:.3rem;">';
          inList = true;
        }
        html += `<li>${formatInline(line.slice(2).trim())}</li>`;
        continue;
      }
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<p style="margin:.45rem 0;">${formatInline(line)}</p>`;
    }
    if (inList) html += "</ul>";
    return html || "<p>—</p>";
  }

  function timeout(ms) {
    return new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms));
  }

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)eduvision_csrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function apiFetch(url, options = {}, ms = 15000) {
    const csrfToken = getCsrfToken();
    const { headers: optHeaders, ...restOptions } = options;
    const mergedHeaders = { Accept: "application/json", ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}), ...(optHeaders || {}) };
    const res = await Promise.race([
      fetch(url, { headers: mergedHeaders, credentials: "include", ...restOptions }),
      timeout(ms),
    ]);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      let detail = data?.detail || data?.message || `Request failed (${res.status})`;
      if (Array.isArray(detail)) {
        const msgs = detail
          .map((x) => (x && typeof x === "object" ? x.msg : null))
          .filter(Boolean);
        detail = msgs.length ? msgs.join(" • ") : "Invalid request.";
      } else if (detail && typeof detail === "object") {
        detail = "Invalid request.";
      }
      const err = new Error(detail);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function ensureToastRoot() {
    let root = document.getElementById(toastRootId);
    if (!root) {
      root = document.createElement("div");
      root.id = toastRootId;
      root.className = "toast-root";
      document.body.appendChild(root);
    }
    return root;
  }

  function showToast(kind, message) {
    const root = ensureToastRoot();
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    const icon = document.createElement("div");
    icon.className = "ticon";
    icon.textContent = kind === "success" ? "✓" : kind === "error" ? "!" : "i";
    const msg = document.createElement("div");
    msg.className = "tmsg";
    msg.innerHTML = escapeHtml(message);
    el.appendChild(icon);
    el.appendChild(msg);
    root.appendChild(el);
    window.setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-6px)";
      el.style.transition = "opacity 220ms ease, transform 220ms ease";
      window.setTimeout(() => el.remove(), 240);
    }, 4000);
  }

  window.toast = {
    success: (m) => showToast("success", m),
    error: (m) => showToast("error", m),
    info: (m) => showToast("info", m),
  };

  function ensureModalRoot() {
    let backdrop = document.querySelector("[data-modal-backdrop]");
    if (backdrop) return backdrop;
    backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.setAttribute("data-modal-backdrop", "true");
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-header">
          <div class="modal-title" id="modal-title"></div>
          <button class="modal-close" type="button" aria-label="Close">×</button>
        </div>
        <div class="modal-body"></div>
      </div>
    `;
    document.body.appendChild(backdrop);

    const close = () => window.modal.close();
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close();
    });
    $(".modal-close", backdrop)?.addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && backdrop.classList.contains("open")) close();
    });
    return backdrop;
  }

  window.modal = {
    open: ({ title, html }) => {
      const backdrop = ensureModalRoot();
      $("#modal-title", backdrop).textContent = title || "Dialog";
      $(".modal-body", backdrop).innerHTML = html || "";
      backdrop.classList.add("open");
    },
    close: () => {
      const backdrop = document.querySelector("[data-modal-backdrop]");
      if (!backdrop) return;
      backdrop.classList.remove("open");
      const body = $(".modal-body", backdrop);
      if (body) body.innerHTML = "";
    },
  };

  function initRipple() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ripple]");
      if (!btn || btn.hasAttribute("disabled") || btn.getAttribute("aria-disabled") === "true") return;
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height) * 1.6;
      const ripple = document.createElement("span");
      ripple.className = "ripple";
      ripple.style.width = `${size}px`;
      ripple.style.height = `${size}px`;
      ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
      ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
      btn.appendChild(ripple);
      window.setTimeout(() => ripple.remove(), 700);
    });
  }

  function initReveal() {
    const els = $all(".reveal");
    if (!els.length) return;
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((en) => en.isIntersecting && en.target.classList.add("visible")),
      { threshold: 0.14 },
    );
    els.forEach((el) => obs.observe(el));
  }

  function initHeroParallax() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const hero = document.querySelector("[data-hero]");
    if (!hero) return;
    const items = Array.from(hero.querySelectorAll("[data-hero-parallax]"));
    if (!items.length) return;

    const base = new Map();
    for (const el of items) {
      base.set(el, el.style.transform || "");
    }

    const onMove = (e) => {
      const rect = hero.getBoundingClientRect();
      const x = (e.clientX - rect.left) / Math.max(1, rect.width) - 0.5;
      const y = (e.clientY - rect.top) / Math.max(1, rect.height) - 0.5;
      for (const el of items) {
        const depth = Number(el.getAttribute("data-depth") || "1");
        const tx = Math.round(x * 14 * depth);
        const ty = Math.round(y * 10 * depth);
        el.style.transform = `${base.get(el)} translate(${tx}px, ${ty}px)`;
      }
    };

    hero.addEventListener("mousemove", onMove);
    hero.addEventListener("mouseleave", () => {
      for (const el of items) el.style.transform = base.get(el) || "";
    });
  }

  function initPageTransitions() {
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (!a) return;
      if (a.target && a.target !== "_self") return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const href = a.getAttribute("href") || "";
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
      e.preventDefault();
      document.body.classList.add("leaving");
      window.setTimeout(() => (window.location.href = url.toString()), 140);
    });
  }

  function initAuthNav() {
    const navAuthed = $("[data-nav-authed]");
    const navAnon = $("[data-nav-anon]");
    const navName = $("[data-nav-name]");
    const logoutBtn = $("[data-logout]");
    if (!navAuthed && !navAnon) return;

    apiFetch("/auth/me")
      .then((me) => {
        const ok = Boolean(me?.authenticated);
        if (navAuthed) navAuthed.style.display = ok ? "" : "none";
        if (navAnon) navAnon.style.display = ok ? "none" : "";
        if (navName && ok) navName.textContent = me?.user?.display_name || "You";
      })
      .catch(() => {});

    if (logoutBtn) {
      logoutBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        try {
          await apiFetch("/auth/logout", { method: "POST" });
          toast.success("Signed out.");
          window.location.href = "/";
        } catch (err) {
          toast.error(err.message || "Could not sign out.");
        }
      });
    }
  }

  function setFieldError(input, msg) {
    const wrap = input.closest("[data-field]");
    input.classList.toggle("error", Boolean(msg));
    if (!wrap) return;
    const err = $("[data-error]", wrap);
    if (err) err.textContent = msg || "";
  }

  function passwordScore(pw) {
    const s = String(pw || "");
    let score = 0;
    if (s.length >= 8) score += 1;
    if (/[A-Z]/.test(s)) score += 1;
    if (/[0-9]/.test(s)) score += 1;
    if (/[^A-Za-z0-9]/.test(s)) score += 1;
    if (s.length >= 14) score += 1;
    return Math.min(5, score);
  }

  function initAuthForms() {
    const form = $("form[data-auth-form]");
    if (!form) return;
    const mode = form.getAttribute("data-auth-form");
    const email = $("input[name=email]", form);
    const password = $("input[name=password]", form);
    const displayName = $("input[name=display_name]", form);
    const btn = $("button[type=submit]", form);
    const resetLink = $("[data-reset-link]", form);
    const strength = $("[data-strength]", form);
    const strengthFill = $("[data-strength-fill]", form);
    const strengthLabel = $("[data-strength-label]", form);

    function openResetModal(prefill) {
      const pre = String(prefill || "").trim();
      window.modal.open({
        title: "Reset your password",
        html: `
          <div class="muted" style="line-height:1.6;">Enter your email and we’ll generate a reset link (dev URL shown).</div>
          <div class="field" style="margin-top:.85rem;">
            <label class="label" for="reset_email">Email</label>
            <input class="input" id="reset_email" type="email" value="${escapeHtml(pre)}" placeholder="you@example.com" />
            <div class="error-text" data-reset-err></div>
          </div>
          <div style="margin-top:1rem; display:flex; justify-content:flex-end; gap:.6rem; flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" data-ripple type="button" data-modal-close>Close</button>
            <button class="btn btn-primary btn-sm" data-ripple type="button" data-reset-send>Send reset link</button>
          </div>
          <div class="muted" data-reset-out style="margin-top:1rem; word-break:break-all;"></div>
        `,
      });
      const backdrop = document.querySelector("[data-modal-backdrop]");
      const closeBtn = backdrop?.querySelector("[data-modal-close]");
      const sendBtn = backdrop?.querySelector("[data-reset-send]");
      const emailEl = backdrop?.querySelector("#reset_email");
      const errEl = backdrop?.querySelector("[data-reset-err]");
      const outEl = backdrop?.querySelector("[data-reset-out]");
      closeBtn?.addEventListener("click", () => window.modal.close(), { once: true });
      sendBtn?.addEventListener(
        "click",
        async () => {
          if (errEl) errEl.textContent = "";
          if (outEl) outEl.textContent = "";
          const em = String(emailEl?.value || "").trim();
          if (!em || !/^\S+@\S+\.\S+$/.test(em)) {
            if (errEl) errEl.textContent = "Enter a valid email.";
            return;
          }
          sendBtn.disabled = true;
          try {
            const res = await apiFetch("/auth/request-password-reset", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email: em }),
            });
            if (res?.reset_url) {
              if (outEl) outEl.innerHTML = `Reset (dev): <a href="${escapeHtml(res.reset_url)}" style="text-decoration:underline; font-weight:900;">${escapeHtml(res.reset_url)}</a>`;
              toast.info("Reset link generated.");
            } else {
              if (outEl) outEl.textContent = "If an account exists, a reset link will be sent.";
              toast.info("If the account exists, you’ll get a link.");
            }
          } catch (err) {
            toast.error(err.message || "Could not request reset.");
          } finally {
            sendBtn.disabled = false;
          }
        },
        { once: false },
      );
    }

    if (mode === "login" && resetLink) {
      resetLink.addEventListener("click", (e) => {
        e.preventDefault();
        openResetModal(email?.value || "");
      });
    }

    const validate = () => {
      let ok = true;
      const em = (email?.value || "").trim();
      if (!em || !/^\S+@\S+\.\S+$/.test(em)) {
        setFieldError(email, "Enter a valid email.");
        ok = false;
      } else setFieldError(email, "");

      const pw = password?.value || "";
      if (!pw || pw.length < 8) {
        setFieldError(password, "At least 8 characters.");
        ok = false;
      } else setFieldError(password, "");

      if (strength && strengthFill && strengthLabel) {
        const sc = passwordScore(pw);
        strength.style.display = "";
        strengthFill.style.width = `${(sc / 5) * 100}%`;
        strengthFill.style.background =
          sc >= 4
            ? "linear-gradient(90deg, var(--color-mint), var(--color-lavender))"
            : sc >= 2
              ? "linear-gradient(90deg, var(--color-peach), var(--color-pink))"
              : "rgb(239 68 68 / 0.9)";
        strengthLabel.textContent = sc >= 4 ? "Strong" : sc >= 2 ? "Okay" : "Weak";
      }

      if (btn) btn.disabled = !ok;
      return ok;
    };

    [email, password].forEach((el) => el && el.addEventListener("input", validate));
    if (displayName) displayName.addEventListener("input", validate);
    validate();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!validate()) {
        form.classList.remove("shake");
        void form.offsetWidth;
        form.classList.add("shake");
        return;
      }
      if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent || "";
        btn.textContent = mode === "login" ? "Logging in..." : "Creating account...";
      }
      try {
        const body = {
          email: (email.value || "").trim(),
          password: password.value || "",
          ...(mode === "signup" ? { display_name: (displayName?.value || "").trim() || null } : {}),
        };
        const endpoint = mode === "login" ? "/auth/login" : "/auth/signup";
        const res = await apiFetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res?.verified && res?.verify_url) {
          toast.info("Verify your email to unlock AI processing.");
          const url = String(res.verify_url);
          window.modal.open({
            title: "Verify your email",
            html: `
              <div class="muted" style="line-height:1.6;">
                In production, we’d email you a verification link. In this dev setup, use the link below:
              </div>
              <div class="card" style="margin-top:.85rem;">
                <div class="card-inner" style="word-break:break-all;">
                  <a href="${escapeHtml(url)}" style="font-weight:900; text-decoration:underline;">${escapeHtml(url)}</a>
                </div>
              </div>
              <div style="margin-top:1rem; display:flex; justify-content:flex-end; gap:.6rem; flex-wrap:wrap;">
                <button class="btn btn-secondary btn-sm" data-ripple type="button" data-modal-close>Close</button>
                <a class="btn btn-primary btn-sm" data-ripple href="/dashboard">Go to dashboard</a>
              </div>
            `,
          });
          const backdrop = document.querySelector("[data-modal-backdrop]");
          backdrop?.querySelector("[data-modal-close]")?.addEventListener("click", () => window.modal.close(), { once: true });
          return;
        } else {
          toast.success("Welcome back.");
        }
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = next || "/dashboard";
      } catch (err) {
        toast.error(err.message || "Authentication failed.");
        if (mode === "login" && String(err.message || "").toLowerCase().includes("no password set")) {
          openResetModal(email?.value || "");
        }
        form.classList.remove("shake");
        void form.offsetWidth;
        form.classList.add("shake");
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = btn.dataset.originalText || "Continue";
        }
      }
    });
  }

  function initUpload() {
    const drop = $("[data-dropzone]");
    const fileInput = $("input[type=file][data-file]");
    const fileCard = $("[data-file-card]");
    const fileName = $("[data-file-name]");
    const removeBtn = $("[data-file-remove]");
    const processBtn = $("[data-process]");
    const processing = $("[data-processing]");
    const progressFill = $("[data-progress-fill]");
    const progressPct = $("[data-progress-pct]");
    const stepText = $("[data-step-text]");
    const stepsList = $("[data-steps]");
    if (!drop || !fileInput || !processBtn) return;

    let currentFile = null;

    function setFile(file) {
      currentFile = file || null;
      if (fileCard) fileCard.style.display = currentFile ? "" : "none";
      if (fileName) fileName.textContent = currentFile ? `${currentFile.name} (${Math.max(1, Math.round(currentFile.size / 1024))}KB)` : "";
      processBtn.disabled = !currentFile;
    }

    drop.addEventListener("click", () => fileInput.click());
    drop.addEventListener("dragover", (e) => (e.preventDefault(), drop.classList.add("dragover")));
    drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("dragover");
      const f = e.dataTransfer?.files?.[0];
      if (f) setFile(f);
    });
    fileInput.addEventListener("change", () => setFile(fileInput.files?.[0] || null));
    if (removeBtn) removeBtn.addEventListener("click", (e) => (e.preventDefault(), setFile(null)));

    async function runProcessing() {
      const steps = [
        { key: "upload", label: "PDF uploaded" },
        { key: "extract", label: "Text extracted" },
        { key: "analyze", label: "Content analyzed" },
        { key: "summary", label: "Generating summary" },
        { key: "quiz", label: "Preparing quiz" },
      ];
      if (stepsList) {
        stepsList.innerHTML = "";
        for (const s of steps) {
          const li = document.createElement("div");
          li.dataset.step = s.key;
          li.className = "muted";
          li.textContent = `⏳ ${s.label}...`;
          stepsList.appendChild(li);
        }
      }

      const intent = ($("input[name=learning_intent]")?.value || "Understand the chapter").trim();
      const data = new FormData();
      data.append("file", currentFile);
      data.append("learningIntent", intent);

      const update = (pct, label, doneKey) => {
        if (progressFill) progressFill.style.width = `${pct}%`;
        if (progressPct) progressPct.textContent = `${pct}%`;
        if (stepText) stepText.textContent = label;
        if (doneKey && stepsList) {
          const row = stepsList.querySelector(`[data-step="${doneKey}"]`);
          if (row) {
            row.className = "";
            row.textContent = `✅ ${row.textContent.replace("⏳ ", "").replace("...", "")}`;
          }
        }
      };

      try {
        update(10, "Uploading your PDF…", "upload");
        await new Promise((r) => setTimeout(r, 260));
        update(35, "Extracting key concepts…", "extract");
        await new Promise((r) => setTimeout(r, 320));
        update(55, "Mapping concepts…", "analyze");

        const result = await apiFetch("/api/process", { method: "POST", body: data }, 120000);
        update(78, "Generating questions…", "summary");
        await new Promise((r) => setTimeout(r, 300));
        update(92, "Final touches…", "quiz");
        await new Promise((r) => setTimeout(r, 220));
        update(100, "Done.", null);
        toast.success("PDF processed successfully!");
        window.setTimeout(() => (window.location.href = `/learn/${encodeURIComponent(result.sessionId)}`), 450);
      } catch (err) {
        const status = err?.status;
        if (status === 401) {
          toast.info("Sign in to process documents.");
          window.location.href = `/login?next=${encodeURIComponent("/upload")}`;
          return;
        }
        if (status === 403) {
          toast.info("Verify your email first, then retry.");
          return;
        }
        toast.error(err.message || "Upload failed. Try again.");
        if (processing) processing.classList.remove("show");
        processBtn.disabled = false;
      }
    }

    processBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      if (!currentFile) return;
      processBtn.disabled = true;
      if (processing) processing.classList.add("show");
      await runProcessing();
    });

    setFile(null);
  }

  function initDashboard() {
    const root = $("[data-dashboard]");
    if (!root) return;
    const welcome = $("[data-welcome]");
    const docs = $("[data-docs]");
    const risk = $("[data-risk]");
    const rec = $("[data-rec]");

    function docCard(d) {
      const el = document.createElement("a");
      el.href = `/learn/${encodeURIComponent(d.id)}`;
      el.className = "card hoverable";
      el.innerHTML = `
        <div class="card-inner">
          <div class="hstack" style="justify-content:space-between;">
            <div style="font-weight:900; letter-spacing:-0.02em;">${escapeHtml(d.title || "Untitled")}</div>
            <span class="badge">${escapeHtml(d.progress_label || "0%")}</span>
          </div>
          <div class="muted" style="margin-top:0.35rem; font-size:0.9rem;">${escapeHtml(d.subtitle || "")}</div>
          <div class="progressbar" style="margin-top:0.85rem;"><div style="width:${Math.max(0, Math.min(100, d.progress || 0))}%"></div></div>
        </div>`;
      return el;
    }

    (async () => {
      try {
        const me = await apiFetch("/auth/me");
        if (!me?.authenticated) {
          window.location.href = `/login?next=${encodeURIComponent("/dashboard")}`;
          return;
        }
        if (!me?.user?.verified) toast.info("Verify your email to unlock AI processing.");
        if (welcome) welcome.textContent = `Welcome back, ${me?.user?.display_name || "friend"}!`;

        const data = await apiFetch("/api/user/documents");
        if (docs) {
          docs.innerHTML = "";
          for (const d of data.documents || []) docs.appendChild(docCard(d));
          if (!(data.documents || []).length) {
            docs.innerHTML = `<div class="card"><div class="card-inner"><div style="font-weight:900;">No PDFs yet</div><div class="muted" style="margin-top:.35rem;">Upload your first document to start your learning journey.</div><div style="margin-top:.85rem;"><a class="btn btn-primary btn-sm" data-ripple href="/upload">Upload a PDF</a></div></div></div>`;
          }
        }

        const riskData = await apiFetch("/api/user/at-risk-concepts").catch(() => ({ concepts: [] }));
        if (risk) {
          risk.innerHTML = "";
          for (const c of (riskData.concepts || []).slice(0, 4)) {
            const row = document.createElement("div");
            row.className = "side-item";
            row.innerHTML = `<div><div style="font-weight:800;">⚠️ ${escapeHtml(c.name || "Concept")}</div><div class="muted" style="font-size:.8rem;">${escapeHtml(c.hint || "Review soon")}</div></div><a class="btn btn-sm" data-ripple href="/learn/${encodeURIComponent(c.session_id)}">Review</a>`;
            risk.appendChild(row);
          }
          if (!(riskData.concepts || []).length) risk.innerHTML = `<div class="muted">No at-risk concepts detected yet.</div>`;
        }

        const recData = await apiFetch("/api/user/recommendations").catch(() => ({ primary_action: "Keep going", secondary_actions: [] }));
        if (rec) {
          rec.innerHTML = `<div style="font-weight:900;">🎯 Next best action</div><div class="muted" style="margin-top:.35rem;">${escapeHtml(recData.primary_action || "Keep going")}</div>`;
          if (recData.session_id) {
            rec.innerHTML += `<div style="margin-top:.85rem;"><a class="btn btn-primary btn-sm btn-pulse" data-ripple href="/learn/${encodeURIComponent(recData.session_id)}">Continue</a></div>`;
          }
        }
      } catch (err) {
        toast.error(err.message || "Could not load dashboard.");
      }
    })();
  }

  function initLearn() {
    const root = $("[data-learn]");
    if (!root) return;
    const sessionId = root.getAttribute("data-session-id");
    const view = root.getAttribute("data-view") || "summary";

    const titleEl = $("[data-learn-title]");
    const summaryEl = $("[data-learn-summary]");
    const conceptsEl = $("[data-learn-concepts]");
    const metaChips = $("[data-learn-meta]");
    const stepBtns = $all("[data-step]", root);
    const stepPanels = $all("[data-panel]", root);
    const masteryLabel = $("[data-mastery-label]");
    const masteryBar = $("[data-mastery-bar]");
    const cogEl = $("[data-cog]");
    const nextEl = $("[data-next]");
    const checkWrap = $("[data-check-questions]");
    const quizConceptSel = $("[data-quiz-concept]");
    const quizDiffSel = $("[data-quiz-diff]");
    const quizTypeSel = $("[data-quiz-type]");
    const quizCountSel = $("[data-quiz-count]");
    const quizGenerateBtn = $("[data-quiz-generate]");
    const quizStatus = $("[data-quiz-status]");
    const quizQuestion = $("[data-quiz-question]");
    const quizOptions = $("[data-quiz-options]");
    const quizAnswer = $("[data-quiz-answer]");
    const quizSubmitBtn = $("[data-quiz-submit]");
    const quizFeedback = $("[data-quiz-feedback]");
    const quizScore = $("[data-quiz-score]");
    const detailedEl = $("[data-detailed]");
    const translateLang = $("[data-translate-lang]");
    const translateBtn = $("[data-translate]");
    const translateOut = $("[data-translate-out]");
    const visualConceptSel = $("[data-visual-concept]");
    const visualGenerateBtn = $("[data-visual-generate]");
    const visualOut = $("[data-visual-out]");

    let cachedSession = null;
    let quizLoaded = false;
    let detailsLoaded = false;
    let currentChunkId = null;
    let currentDifficulty = "medium";
    let questionStart = 0;

    function show(which) {
      stepBtns.forEach((b) => b.classList.toggle("active", b.getAttribute("data-step") === which));
      stepPanels.forEach((p) => (p.style.display = p.getAttribute("data-panel") === which ? "" : "none"));
      const url =
        which === "summary"
          ? `/learn/${encodeURIComponent(sessionId)}`
          : which === "quiz"
            ? `/learn/${encodeURIComponent(sessionId)}/quiz`
            : `/learn/${encodeURIComponent(sessionId)}/details`;
      history.replaceState({}, "", url);
      if (which === "quiz") void loadQuiz();
      if (which === "details") void loadDetails();
    }

    stepBtns.forEach((b) =>
      b.addEventListener("click", (e) => {
        e.preventDefault();
        show(b.getAttribute("data-step"));
      }),
    );

    function renderConcepts(concepts) {
      if (!conceptsEl) return;
      conceptsEl.innerHTML = "";
      for (const c of concepts) {
        const d = document.createElement("details");
        d.className = "card";
        d.style.overflow = "hidden";
        d.innerHTML = `
          <summary class="card-inner" style="cursor:pointer; list-style:none; display:flex; align-items:center; justify-content:space-between;">
            <div>
              <div style="font-weight:900; letter-spacing:-0.01em;">${escapeHtml(c.title || c.name || "Concept")}</div>
              <div class="muted" style="font-size:.86rem; margin-top:.15rem;">${escapeHtml(c.summary || "")}</div>
            </div>
            <span class="badge">${escapeHtml(c.status || "locked")}</span>
          </summary>
          <div class="card-inner" style="border-top:1px solid rgb(17 24 39 / 0.06);">
            <div class="muted" style="white-space:pre-wrap; line-height:1.6;">${escapeHtml(c.content || "—")}</div>
          </div>`;
        conceptsEl.appendChild(d);
      }
    }

    (async () => {
      try {
        const me = await apiFetch("/auth/me");
        if (!me?.authenticated) {
          window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
          return;
        }
        const data = await apiFetch(`/api/session/${encodeURIComponent(sessionId)}`);
        const s = data.session || {};
        cachedSession = s;
        if (titleEl) titleEl.textContent = s.filename || "Learning Session";
        if (summaryEl) summaryEl.innerHTML = renderMarkdown((s.summary || "").trim());

        const concepts = Array.isArray(s.concepts) ? s.concepts : [];
        renderConcepts(concepts);

        if (quizConceptSel) {
          quizConceptSel.innerHTML = "";
          const opt0 = document.createElement("option");
          opt0.value = "";
          opt0.textContent = "Select a concept…";
          quizConceptSel.appendChild(opt0);
          for (const c of concepts) {
            const o = document.createElement("option");
            o.value = c.id || "";
            o.textContent = c.title || c.name || "Concept";
            quizConceptSel.appendChild(o);
          }
        }

        if (visualConceptSel) {
          visualConceptSel.innerHTML = "";
          for (const c of concepts) {
            const o = document.createElement("option");
            o.value = c.id || "";
            o.textContent = c.title || c.name || "Concept";
            visualConceptSel.appendChild(o);
          }
        }

        if (metaChips) {
          metaChips.innerHTML = "";
          const chip = (t) => {
            const el = document.createElement("span");
            el.className = "badge";
            el.textContent = t;
            return el;
          };
          metaChips.appendChild(chip(`Concepts: ${concepts.length}`));
          const avg = concepts.length ? Math.round(concepts.reduce((a, c) => a + (c.score || 0), 0) / concepts.length) : 0;
          metaChips.appendChild(chip(`Mastery: ${avg}%`));
          if (masteryLabel) masteryLabel.textContent = `${avg}%`;
          if (masteryBar) masteryBar.style.width = `${avg}%`;
        }

        if (cogEl) {
          apiFetch("/api/cognitive-status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          })
            .then((c) => {
              cogEl.innerHTML = `<div style="font-weight:900;">⚡ Cognitive load</div><div class="muted" style="margin-top:.35rem;">${escapeHtml(c.message || "In the zone")}</div>${c.action ? `<div style="margin-top:.6rem;"><span class="badge">${escapeHtml(c.action)}</span></div>` : ""}`;
            })
            .catch(() => {});
        }

        if (nextEl) {
          apiFetch("/api/next-steps", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          })
            .then((n) => {
              nextEl.innerHTML = `<div style="font-weight:900;">🎯 Next steps</div><div class="muted" style="margin-top:.35rem;">${escapeHtml(n.primary_action || "")}</div>${(n.secondary_actions || []).length ? `<div style="margin-top:.6rem;" class="muted">${escapeHtml(n.secondary_actions.join(" • "))}</div>` : ""}`;
            })
            .catch(() => {});
        }

        show(view);
      } catch (err) {
        toast.error(err.message || "Could not load session.");
      }
    })();

    async function loadQuiz() {
      if (quizLoaded) return;
      quizLoaded = true;

      if (checkWrap) {
        try {
          const q = await apiFetch(`/api/session/${encodeURIComponent(sessionId)}/check-questions`, {}, 25000);
          const qs = Array.isArray(q.questions) ? q.questions : [];
          checkWrap.innerHTML = "";
          for (const item of qs.slice(0, 4)) {
            const d = document.createElement("details");
            d.className = "card";
            d.style.overflow = "hidden";
            d.innerHTML = `
              <summary class="card-inner" style="cursor:pointer; list-style:none;">
                <div style="font-weight:900;">${escapeHtml(item.question || "Question")}</div>
                <div class="muted" style="margin-top:.2rem; font-size:.85rem;">Click to reveal answer</div>
              </summary>
              <div class="card-inner" style="border-top:1px solid rgb(17 24 39 / 0.06);">
                <div><strong>Answer:</strong> ${escapeHtml(item.correct_answer || "—")}</div>
                <div style="margin-top:.35rem;"><strong>Why:</strong> ${escapeHtml(item.explanation || "—")}</div>
              </div>`;
            checkWrap.appendChild(d);
          }
          if (!qs.length) checkWrap.innerHTML = `<div class="muted">No quick checks yet.</div>`;
        } catch (err) {
          checkWrap.innerHTML = `<div class="muted">Could not load quick checks.</div>`;
        }
      }

      let quizRemaining = 0;

      async function doGenerateQuiz() {
        const chunkId = quizConceptSel?.value || "";
        const difficulty = quizDiffSel?.value || "medium";
        const questionType = (quizTypeSel?.value || "").trim() || null;
        if (!chunkId) return toast.info("Pick a concept first.");
        currentChunkId = chunkId;
        currentDifficulty = difficulty;
        questionStart = Date.now();
        if (quizStatus) quizStatus.textContent = quizRemaining > 0 ? `Generating… (${quizRemaining} left)` : "Generating…";
        if (quizQuestion) quizQuestion.textContent = "—";
        if (quizFeedback) quizFeedback.textContent = "";
        if (quizScore) quizScore.style.display = "none";
        if (quizAnswer) quizAnswer.value = "";
        if (quizOptions) { quizOptions.style.display = "none"; quizOptions.innerHTML = ""; }
        const answerField = quizAnswer?.closest(".field");
        if (answerField) answerField.style.display = "";
        try {
          if (quizGenerateBtn) quizGenerateBtn.disabled = true;
          const res = await apiFetch("/api/generate-quiz", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chunk_id: chunkId, difficulty, question_type: questionType }),
          }, 45000);
          const payload = res.question && typeof res.question === "object" ? res.question : null;
          const qText = payload?.question ? String(payload.question) : String(res.question || "Question generated.");
          if (quizQuestion) quizQuestion.textContent = qText;
          const format = String(payload?.format || "");
          const options = Array.isArray(payload?.options) ? payload.options : [];
          if ((format === "multiple_choice" || questionType === "mcq") && options.length && quizOptions) {
            quizOptions.style.display = "grid";
            quizOptions.innerHTML = "";
            const af = quizAnswer?.closest(".field");
            if (af) af.style.display = "none";
            for (const opt of options.slice(0, 4)) {
              const b = document.createElement("button");
              b.type = "button";
              b.className = "btn btn-secondary btn-sm";
              b.setAttribute("data-ripple", "true");
              b.textContent = String(opt);
              b.addEventListener("click", () => {
                if (quizAnswer) quizAnswer.value = String(opt);
                Array.from(quizOptions.querySelectorAll("button")).forEach((x) => (x.style.outline = "none"));
                b.style.outline = "2px solid var(--ink)";
                b.style.outlineOffset = "2px";
              });
              quizOptions.appendChild(b);
            }
          } else {
            const af = quizAnswer?.closest(".field");
            if (af) af.style.display = "";
            if (quizAnswer) {
              if (format === "one_word" || questionType === "one_word") quizAnswer.placeholder = "One word…";
              else if (format === "one_sentence" || questionType === "one_sentence") quizAnswer.placeholder = "One sentence…";
              else if (format === "fill_blank" || questionType === "fill_blank") quizAnswer.placeholder = "Fill the blank…";
              else quizAnswer.placeholder = "Type your answer…";
            }
          }
          if (quizStatus) quizStatus.textContent = "";
          void apiFetch("/api/track-event", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, chunk_id: chunkId, event_type: "quiz_generate", payload: { difficulty, question_type: questionType } }),
          }).catch(() => {});
        } catch (err) {
          toast.error(err.message || "Failed to generate.");
          if (quizStatus) quizStatus.textContent = "Failed to generate.";
        } finally {
          if (quizGenerateBtn) quizGenerateBtn.disabled = false;
        }
      }

      if (quizGenerateBtn) {
        quizGenerateBtn.addEventListener("click", () => {
          quizRemaining = parseInt(quizCountSel?.value || "1", 10) - 1;
          doGenerateQuiz();
        });
      }

      if (quizSubmitBtn) {
        quizSubmitBtn.addEventListener("click", async () => {
          const chunkId = currentChunkId || (quizConceptSel?.value || "");
          const difficulty = currentDifficulty || (quizDiffSel?.value || "medium");
          const questionType = (quizTypeSel?.value || "").trim() || null;
          const ans = (quizAnswer?.value || "").trim();
          if (!chunkId) return toast.info("Generate a question first.");
          if (!ans) return toast.info("Type an answer first.");
          const timeTaken = Math.max(0, Date.now() - (questionStart || Date.now()));
          if (quizStatus) quizStatus.textContent = "Checking…";
          try {
            quizSubmitBtn.disabled = true;
            const res = await apiFetch("/api/submit-quiz", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ chunk_id: chunkId, user_answer: ans, difficulty, time_taken_ms: timeTaken, question_type: questionType }),
            }, 60000);
            if (quizScore) {
              quizScore.style.display = "";
              quizScore.textContent = `${res.score ?? 0}%`;
            }
            if (quizFeedback) quizFeedback.innerHTML = renderMarkdown(String(res.feedback || "—"));
            toast.success(res.mastered ? "Mastered! Great job." : "Checked.");
            if (quizStatus) quizStatus.textContent = "";
            void apiFetch("/api/track-event", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_id: sessionId, chunk_id: chunkId, event_type: "quiz_submit", payload: { score: res.score, difficulty, time_taken_ms: timeTaken, question_type: questionType } }),
            }).catch(() => {});
            try {
              const updated = await apiFetch(`/api/session/${encodeURIComponent(sessionId)}`);
              cachedSession = updated.session || cachedSession;
              const concepts = Array.isArray(cachedSession?.concepts) ? cachedSession.concepts : [];
              const avg = concepts.length ? Math.round(concepts.reduce((a, c) => a + (c.score || 0), 0) / concepts.length) : 0;
              if (masteryLabel) masteryLabel.textContent = `${avg}%`;
              if (masteryBar) masteryBar.style.width = `${avg}%`;
            } catch { /* ignore */ }
            if (quizRemaining > 0) {
              quizRemaining--;
              setTimeout(() => doGenerateQuiz(), 800);
            }
          } catch (err) {
            toast.error(err.message || "Could not submit.");
            if (quizStatus) quizStatus.textContent = "Could not check.";
          } finally {
            quizSubmitBtn.disabled = false;
          }
        });
      }
    }

    async function loadDetails() {
      if (detailsLoaded) return;
      detailsLoaded = true;
      if (detailedEl) {
        try {
          const d = await apiFetch(`/api/session/${encodeURIComponent(sessionId)}/detailed-summary`, {}, 60000);
          detailedEl.innerHTML = renderMarkdown((d.detailed_summary || "").trim());
        } catch (err) {
          detailedEl.innerHTML = `<div class="muted">Could not load detailed summary.</div>`;
        }
      }

      if (translateBtn) {
        translateBtn.addEventListener("click", async () => {
          const lang = (translateLang?.value || "").trim();
          if (!lang) return toast.info("Enter a target language (e.g., Hindi).");
          if (translateOut) translateOut.innerHTML = `<div class="muted">Translating…</div>`;
          translateBtn.disabled = true;
          try {
            const t = await apiFetch(`/api/session/${encodeURIComponent(sessionId)}/translate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ target_language: lang }),
            }, 90000);
            if (translateOut) translateOut.innerHTML = renderMarkdown((t.translated_text || "").trim());
          } catch (err) {
            if (translateOut) translateOut.innerHTML = `<div class="muted">Translate failed.</div>`;
            toast.error(err.message || "Translate failed.");
          } finally {
            translateBtn.disabled = false;
          }
        });
      }

      if (visualGenerateBtn) {
        visualGenerateBtn.addEventListener("click", async () => {
          const conceptId = visualConceptSel?.value || "";
          const concepts = Array.isArray(cachedSession?.concepts) ? cachedSession.concepts : [];
          const c = concepts.find((x) => x && x.id === conceptId) || concepts[0];
          const text = String(c?.content || c?.summary || c?.title || c?.name || cachedSession?.summary || "").trim();
          if (!text) return toast.info("No concept text available.");
          if (visualOut) visualOut.innerHTML = `<div class="muted">Generating…</div>`;
          visualGenerateBtn.disabled = true;
          try {
            const res = await apiFetch("/api/visual-image", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text }),
            });
            if (res.image_url) {
              if (visualOut) {
                visualOut.innerHTML = `
                  <div style="display:grid; gap:1rem; align-items:start;">
                    <img src="${escapeHtml(res.image_url)}" alt="Generated visual" style="width:100%; border-radius:0.75rem; max-height:500px; object-fit:cover; box-shadow:0 4px 12px rgb(0 0 0 / 0.15); border:1px solid rgb(229 231 235 / 1);">
                    <div style="font-size:0.875rem; color:rgb(107 114 128 / 1); line-height:1.5;">
                      <strong>Visual:</strong> ${escapeHtml(res.search_query || "")}</div>
                  </div>
                `;
              }
              toast.success("Visual generated!");
            } else {
              if (visualOut) visualOut.innerHTML = `<div class="muted">Could not generate visual.</div>`;
              toast.error("Failed to generate visual.");
            }
          } catch (err) {
            if (visualOut) visualOut.innerHTML = `<div class="muted">—</div>`;
            toast.error(err.message || "Could not generate visual image.");
          } finally {
            visualGenerateBtn.disabled = false;
          }
        });
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initPageTransitions();
    initRipple();
    initReveal();
    initHeroParallax();
    initAuthNav();
    initAuthForms();
    initUpload();
    initDashboard();
    initLearn();
  });
})();
