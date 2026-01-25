// =====================================
// UI Helpers ONLY (No Chat, No Location)
// =====================================

// Toggle the mobile navigation menu
function toggleMobileMenu() {
  const menu = document.getElementById("nav-menu");
  if (!menu) return;
  menu.classList.toggle("is-open");
}
window.toggleMobileMenu = toggleMobileMenu;

// Close mobile menu when a link is clicked
function wireNavLinks() {
  const menu = document.getElementById("nav-menu");
  if (!menu) return;

  menu.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", () => {
      menu.classList.remove("is-open");
    });
  });
}

// Smooth scroll for in-page anchors
function enableSmoothScroll() {
  document.querySelectorAll("a[href^='#']").forEach(anchor => {
    anchor.addEventListener("click", (e) => {
      const targetId = anchor.getAttribute("href").slice(1);
      const target = document.getElementById(targetId);
      if (!target) return;

      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

// Add shadow to navbar on scroll
function handleScrollShadow() {
  const navbar = document.getElementById("navbar");
  if (!navbar) return;

  const onScroll = () => {
    navbar.classList.toggle("has-shadow", window.scrollY > 8);
  };

  onScroll();
  window.addEventListener("scroll", onScroll);
}

// ------------------------------
// Init on DOM ready
// ------------------------------
document.addEventListener("DOMContentLoaded", () => {
  wireNavLinks();
  enableSmoothScroll();
  handleScrollShadow();
});
document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  addUserMessage(msg);
  input.value = "";

  let url = "/chat";
  let payload = { stage: chatStage, message: msg };

  // PIN FLOW
  if (chatStage === "ASK_LOCATION_TEXT") {
    url = "/chat/pin";
    payload = { pin: msg };
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  chatStage = data.stage;
  addBotMessage(data.reply);
});
document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  addUserMessage(msg);
  input.value = "";

  let url = "/chat";
  let payload = { stage: chatStage, message: msg };

  // PIN FLOW
  if (chatStage === "ASK_LOCATION_TEXT") {
    url = "/chat/pin";
    payload = { pin: msg };
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  chatStage = data.stage;
  addBotMessage(data.reply);
});
document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  addUserMessage(msg);
  input.value = "";
  let url = "/chat";
  let payload = { stage: chatStage, message: msg };
  // PIN FLOW
  if (chatStage === "ASK_LOCATION_TEXT") {
	url = "/chat/pin";
	payload = { pin: msg };
  }
  const res = await fetch(url, {
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(payload)
	  });
	    const data = await res.json();
	  
		  chatStage = data.stage;
		  addBotMessage(data.reply);
	});