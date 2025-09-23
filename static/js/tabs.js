document.addEventListener('DOMContentLoaded', () => {
  const groups = new Map();

  document.querySelectorAll('[data-tab-target]').forEach((trigger) => {
    const groupName = trigger.getAttribute('data-tab-group') || 'default';
    if (!groups.has(groupName)) {
      groups.set(groupName, { triggers: [], contents: new Map() });
    }

    const group = groups.get(groupName);
    group.triggers.push(trigger);

    const targetId = trigger.getAttribute('data-tab-target');
    if (targetId && !group.contents.has(targetId)) {
      const content = document.getElementById(targetId);
      if (content) {
        group.contents.set(targetId, content);
      }
    }
  });

  groups.forEach(({ triggers, contents }) => {
    const contentList = Array.from(contents.values());

    triggers.forEach((trigger) => {
      trigger.addEventListener('click', (event) => {
        const targetId = trigger.getAttribute('data-tab-target');
        if (!targetId) {
          return;
        }

        const targetContent = contents.get(targetId);
        if (!targetContent) {
          return;
        }

        if (trigger.tagName === 'A') {
          const href = trigger.getAttribute('href');
          if (href && href !== '#' && !href.startsWith('#')) {
            return;
          }
          event.preventDefault();
        } else {
          event.preventDefault();
        }

        triggers.forEach((btn) => {
          btn.classList.remove('border-indigo-500', 'text-indigo-600');
          btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
          btn.setAttribute('aria-selected', 'false');
        });

        contentList.forEach((content) => {
          content.classList.add('hidden');
        });

        targetContent.classList.remove('hidden');
        trigger.classList.add('border-indigo-500', 'text-indigo-600');
        trigger.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
        trigger.setAttribute('aria-selected', 'true');
      });
    });
  });
});