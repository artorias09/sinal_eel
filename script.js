document.addEventListener('DOMContentLoaded', () => {

  /* ---------- Ano dinâmico no rodapé ---------- */
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* ---------- Header muda de estilo ao rolar ---------- */
  const header = document.getElementById('site-header');
  const onScroll = () => {
    if (window.scrollY > 12) {
      header.classList.add('is-scrolled');
    } else {
      header.classList.remove('is-scrolled');
    }
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ---------- Menu mobile ---------- */
  const navToggle = document.getElementById('nav-toggle');
  const mainNav = document.getElementById('main-nav');

  navToggle.addEventListener('click', () => {
    const isOpen = mainNav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });

  mainNav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      mainNav.classList.remove('is-open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });

  /* ---------- Lista de bairros monitorados ---------- */
  const bairros = [
    'Ponte Nova',
    'Vila Portugal',
    'Vila Nunes',
    'Bairro da Cruz',
    'Vila Passos',
    'Vila Santa Edwiges',
    'Vila Geny',
    'Olaria',
    'Cidade Industrial',
    'Centro'
  ];

  const grid = document.getElementById('neighborhood-grid');
  if (grid) {
    grid.innerHTML = bairros.map((nome, i) => `
      <li class="neighborhood-chip">
        <span class="chip-index">B${String(i + 1).padStart(2, '0')}</span>
        <span class="chip-name">${nome}</span>
      </li>
    `).join('');
  }

  /* ---------- Reveal on scroll (cards) ---------- */
  const revealTargets = document.querySelectorAll('.step-card, .event-card, .neighborhood-chip');

  if ('IntersectionObserver' in window && revealTargets.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    revealTargets.forEach((el) => observer.observe(el));
  } else {
    // Fallback: mostra tudo direto, sem animação
    revealTargets.forEach((el) => el.classList.add('in-view'));
  }

});
