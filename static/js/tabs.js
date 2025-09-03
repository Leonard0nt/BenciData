document.addEventListener('DOMContentLoaded', () => {
  const tabButtons = document.querySelectorAll('[data-tab-target]');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab-target');

      // desactivar todos los botones
      tabButtons.forEach((b) => {
        b.classList.remove('border-indigo-500', 'text-indigo-600');
        b.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
      });

      // ocultar todos los contenidos
      tabContents.forEach((content) => {
        content.classList.add('hidden');
      });

      // activar el tab clicado
      document.getElementById(targetId).classList.remove('hidden');
      btn.classList.add('border-indigo-500', 'text-indigo-600');
      btn.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
    });
  });
});
