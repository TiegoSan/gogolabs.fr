(function () {
  const trackedHostnames = new Set(["gogolabs.fr", "www.gogolabs.fr"]);

  if (!trackedHostnames.has(window.location.hostname)) {
    return;
  }

  const script = document.createElement("script");
  script.defer = true;
  script.src = "https://stats.gogolabs.fr/script.js";
  script.dataset.websiteId = "120e76d3-42e2-4463-8098-781e5417f478";
  document.head.appendChild(script);
})();
