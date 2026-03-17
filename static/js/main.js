function handleScrollShadow() {
  const navbar = document.getElementById("navbar");
  if (!navbar) return;

  const onScroll = () => {
    navbar.classList.toggle("has-shadow", window.scrollY > 8);
  };

  onScroll();
  window.addEventListener("scroll", onScroll);
}

document.addEventListener("DOMContentLoaded", () => {
  handleScrollShadow();
});
