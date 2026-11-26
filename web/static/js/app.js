const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function onReady(fn) {
  if (document.readyState !== "loading") fn();
  else document.addEventListener("DOMContentLoaded", fn);
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function initSpotlight() {
  document.querySelectorAll(".spotlight").forEach((card) => {
    card.addEventListener("mousemove", (event) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${event.clientX - rect.left}px`);
      card.style.setProperty("--my", `${event.clientY - rect.top}px`);
    });
  });
}

function initTilt() {
  if (reduceMotion) return;
  document.querySelectorAll("[data-tilt]").forEach((card) => {
    card.addEventListener("mousemove", (event) => {
      const rect = card.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `perspective(900px) rotateX(${(-py * 4).toFixed(2)}deg) rotateY(${(px * 5).toFixed(2)}deg) translateY(-2px)`;
    });
    card.addEventListener("mouseleave", () => {
      card.style.transform = "";
    });
  });
}

function initMagnetic() {
  if (reduceMotion) return;
  document.querySelectorAll(".magnetic").forEach((element) => {
    element.addEventListener("mousemove", (event) => {
      const rect = element.getBoundingClientRect();
      const x = (event.clientX - rect.left - rect.width / 2) * 0.16;
      const y = (event.clientY - rect.top - rect.height / 2) * 0.22;
      element.style.transform = `translate(${x}px, ${y}px)`;
    });
    element.addEventListener("mouseleave", () => {
      element.style.transform = "";
    });
  });
}

function animateCount(element) {
  const target = Number(element.dataset.target || element.textContent || 0);
  if (!Number.isFinite(target)) return;
  const duration = 1100;
  const start = performance.now();
  function frame(now) {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = String(Math.round(target * eased));
    if (progress < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function initCounts() {
  const nodes = document.querySelectorAll(".count");
  if (!nodes.length) return;
  if (reduceMotion) {
    nodes.forEach((node) => (node.textContent = node.dataset.target || node.textContent));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCount(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });
  nodes.forEach((node) => observer.observe(node));
}

function initToasts() {
  const toasts = document.querySelectorAll(".toast");
  toasts.forEach((toast, index) => {
    setTimeout(() => {
      toast.style.transition = "opacity .3s, transform .3s";
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-8px)";
      setTimeout(() => toast.remove(), 320);
    }, 4200 + index * 300);
  });
}

function initRail() {
  const toggle = document.getElementById("rail-toggle");
  const rail = document.getElementById("rail");
  if (!toggle || !rail) return;
  toggle.addEventListener("click", () => rail.classList.toggle("open"));
  document.addEventListener("click", (event) => {
    if (window.innerWidth > 900) return;
    if (!rail.contains(event.target) && !toggle.contains(event.target)) rail.classList.remove("open");
  });
}

function initSearchShortcut() {
  const input = document.querySelector(".search-box input");
  if (!input) return;
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      input.focus();
    }
  });
}

function initComposer() {
  document.querySelectorAll("textarea[data-autosize]").forEach((area) => {
    const resize = () => {
      area.style.height = "auto";
      area.style.height = `${Math.min(area.scrollHeight, 340)}px`;
    };
    area.addEventListener("input", resize);
    resize();
  });
}

function initTheme() {
  const button = document.getElementById("theme-toggle");
  if (!button) return;
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("campus-theme", theme); } catch (error) { /* storage blocked */ }
    const meta = document.getElementById("theme-color");
    if (meta) meta.content = theme === "dark" ? "#0f1226" : "#dcd6f7";
    button.innerHTML = theme === "dark" ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
    refreshIcons();
  };
  apply(document.documentElement.dataset.theme || "light");
  button.addEventListener("click", () => {
    apply(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  });
}

function initLightbox() {
  const items = document.querySelectorAll("[data-lightbox]");
  if (!items.length) return;
  const overlay = document.createElement("div");
  overlay.className = "lightbox";
  overlay.innerHTML = '<div class="lightbox-inner">' +
    '<div class="lightbox-media"></div>' +
    '<div class="lightbox-controls">' +
      '<a class="lightbox-download" download href="#" aria-label="Download"><i data-lucide="download"></i></a>' +
      '<button class="lightbox-close" type="button" aria-label="Close"><i data-lucide="x"></i></button>' +
    '</div></div>';
  document.body.appendChild(overlay);
  const media = overlay.querySelector(".lightbox-media");
  const download = overlay.querySelector(".lightbox-download");
  const close = () => { overlay.classList.remove("open"); media.innerHTML = ""; };

  items.forEach((item) => {
    item.addEventListener("click", (event) => {
      if (event.target.closest(".media-actions")) return;
      const src = item.dataset.src || item.src || item.querySelector("img, video")?.src;
      const isVideo = (item.dataset.type || "").startsWith("video");
      media.innerHTML = isVideo
        ? `<video controls src="${src}"></video>`
        : `<img src="${src}" alt="preview">`;
      download.href = src;
      download.setAttribute("download", src.split("/").pop() || "media");
      overlay.classList.add("open");
    });
  });
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || event.target.closest(".lightbox-close") || event.target.closest(".lightbox-download")) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && overlay.classList.contains("open")) close();
  });
  refreshIcons();
}

function toast(message, isError) {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const node = document.createElement("div");
  node.className = "toast" + (isError ? " err" : "");
  node.textContent = message;
  stack.appendChild(node);
  setTimeout(() => { node.style.opacity = "0"; setTimeout(() => node.remove(), 320); }, 4000);
}

async function refreshComments(post) {
  const postId = post.id.replace("post-", "");
  const response = await fetch(`/posts/${postId}/comments`);
  const html = await response.text();
  const holder = document.createElement("div");
  holder.innerHTML = html;
  const fresh = holder.querySelector(".comment-list-wrap");
  const current = post.querySelector(".comment-list-wrap");
  if (fresh && current) current.replaceWith(fresh);
  refreshIcons();
}

function initAjaxActions() {
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-ajax]");
    if (!form) return;
    event.preventDefault();
    const kind = form.dataset.ajax;
    const post = form.closest(".post");
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "fetch" },
      });
      const data = await response.json();
      if (!data.ok) { toast(data.message || "That did not work.", true); return; }
      if ((kind === "like" || kind === "unlike") && post) {
        const pill = form.querySelector("button.pill");
        if (pill) {
          pill.classList.toggle("liked", Boolean(data.liked));
          pill.innerHTML = `<i data-lucide="heart"></i> ${data.likes}`;
        }
        refreshIcons();
      } else if ((kind === "save" || kind === "unsave") && post) {
        const pill = form.querySelector("button.pill");
        if (pill) {
          pill.classList.toggle("saved", Boolean(data.saved));
          pill.innerHTML = data.saved
            ? '<i data-lucide="bookmark-check"></i> Saved'
            : '<i data-lucide="bookmark"></i> Save';
        }
        refreshIcons();
      } else if (kind === "comment" || kind === "delete-comment") {
        if (kind === "comment") form.reset();
        if (post) {
          await refreshComments(post);
          const count = post.querySelector('a[href$="-comments"]');
          if (count && typeof data.comment_count === "number") {
            count.innerHTML = `<i data-lucide="message-circle"></i> ${data.comment_count}`;
          }
        }
        refreshIcons();
      }
      if (data.message && kind !== "like" && kind !== "unlike" && kind !== "save" && kind !== "unsave") {
        toast(data.message);
      }
    } catch (error) {
      toast("Could not reach the server.", true);
    } finally {
      if (button) button.disabled = false;
    }
  });
}

function initGSAP() {
  if (!window.gsap || reduceMotion) return;
  if (window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);

  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
  if (document.querySelector(".rail")) tl.from(".rail", { x: -26, autoAlpha: 0, duration: 0.7 });
  if (document.querySelector(".topbar")) tl.from(".topbar", { y: -18, autoAlpha: 0, duration: 0.6 }, "-=0.45");
  if (document.querySelector(".page-head")) tl.from(".page-head > *", { y: 24, autoAlpha: 0, stagger: 0.08, duration: 0.65 }, "-=0.3");

  const reveals = gsap.utils.toArray(".reveal");
  reveals.forEach((element, index) => {
    gsap.from(element, {
      y: 26,
      autoAlpha: 0,
      duration: 0.7,
      delay: Math.min(index * 0.05, 0.4),
      ease: "power3.out",
      clearProps: "transform",
    });
  });

  if (window.ScrollTrigger) {
    gsap.utils.toArray(".scroll-reveal").forEach((element) => {
      gsap.from(element, {
        y: 32,
        autoAlpha: 0,
        duration: 0.8,
        ease: "power3.out",
        scrollTrigger: { trigger: element, start: "top 88%" },
      });
    });
    gsap.utils.toArray(".stagger").forEach((group) => {
      gsap.from(group.children, {
        y: 26,
        autoAlpha: 0,
        duration: 0.6,
        stagger: 0.08,
        ease: "power3.out",
        scrollTrigger: { trigger: group, start: "top 85%" },
      });
    });
  }
}

onReady(() => {
  initTheme();
  refreshIcons();
  initSpotlight();
  initTilt();
  initMagnetic();
  initCounts();
  initToasts();
  initRail();
  initSearchShortcut();
  initComposer();
  initLightbox();
  initAjaxActions();
  initGSAP();
});
