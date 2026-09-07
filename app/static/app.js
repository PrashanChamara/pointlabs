const root=document.documentElement;
document.querySelector('[data-theme-toggle]')?.addEventListener('click',()=>{const next=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=next;localStorage.setItem('pointlabs-theme',next)});
document.querySelector('[data-menu-toggle]')?.addEventListener('click',()=>document.querySelector('#sidebar')?.classList.toggle('open'));
