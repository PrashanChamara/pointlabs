const root = document.documentElement;
const sidebar = document.querySelector('#sidebar');
const menuButton = document.querySelector('[data-menu-toggle]');
const closeButton = document.querySelector('[data-menu-close]');
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

if (csrfToken) {
  document.querySelectorAll('form').forEach((form) => {
    if ((form.method || 'get').toLowerCase() !== 'post' || form.querySelector('input[name="csrf_token"]')) return;
    const tokenField = document.createElement('input');
    tokenField.type = 'hidden';
    tokenField.name = 'csrf_token';
    tokenField.value = csrfToken;
    form.prepend(tokenField);
  });
}

document.querySelector('[data-theme-toggle]')?.addEventListener('click', () => {
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  root.dataset.theme = next;
  localStorage.setItem('pointlabs-theme', next);
});

const closeMenu = () => {
  sidebar?.classList.remove('open');
  menuButton?.setAttribute('aria-expanded', 'false');
};

menuButton?.addEventListener('click', () => {
  const isOpen = sidebar?.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(Boolean(isOpen)));
});
closeButton?.addEventListener('click', closeMenu);

document.addEventListener('click', (event) => {
  if (window.innerWidth <= 680 && sidebar?.classList.contains('open') && !sidebar.contains(event.target) && !menuButton?.contains(event.target)) closeMenu();
});
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeMenu(); });
window.addEventListener('resize', () => { if (window.innerWidth > 680) closeMenu(); });
sidebar?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => { if (window.innerWidth <= 680) closeMenu(); }));
