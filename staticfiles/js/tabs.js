document.addEventListener('DOMContentLoaded', () => {
  const groups = new Map();

  const ensureContent = (group, targetId) => {
    if (!targetId || group.contents.has(targetId)) {
      return;
    }

    const content = document.getElementById(targetId);
    if (content) {
      group.contents.set(targetId, content);
    }
  };

  const activateTab = (group, trigger, targetId) => {
    const targetContent = group.contents.get(targetId);
    if (!targetContent) {
      return;
    }

    group.triggers.forEach((btn) => {
      btn.classList.remove('border-indigo-500', 'text-indigo-600');
      btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
      btn.setAttribute('aria-selected', 'false');
    });

    group.contents.forEach((content) => {
      content.classList.add('hidden');
    });

    targetContent.classList.remove('hidden');
    trigger.classList.add('border-indigo-500', 'text-indigo-600');
    trigger.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
    trigger.setAttribute('aria-selected', 'true');
  };

  document.querySelectorAll('[data-tab-target]').forEach((trigger) => {
    const groupName = trigger.getAttribute('data-tab-group') || 'default';
    const targetId = trigger.getAttribute('data-tab-target');

    if (!groups.has(groupName)) {
      groups.set(groupName, { triggers: [], contents: new Map() });
    }

    const group = groups.get(groupName);
    group.triggers.push(trigger);
    ensureContent(group, targetId);

    trigger.addEventListener('click', (event) => {
      if (!targetId) {
        return;
      }


      if (trigger.tagName === 'A') {
        const href = trigger.getAttribute('href');
        if (href && href !== '#' && !href.startsWith('#')) {
          return;
        }
      }

      event.preventDefault();
      ensureContent(group, targetId);
      activateTab(group, trigger, targetId);
    });
  });

  groups.forEach((group) => {
    const initiallySelected = group.triggers.find(
      (trigger) => trigger.getAttribute('aria-selected') === 'true',
    );

    if (initiallySelected) {
      const targetId = initiallySelected.getAttribute('data-tab-target');
      ensureContent(group, targetId);
      activateTab(group, initiallySelected, targetId);
      return;
    }

    if (group.triggers.length === 0) {
      return;
    }

    const firstTrigger = group.triggers[0];
    const targetId = firstTrigger.getAttribute('data-tab-target');
    ensureContent(group, targetId);
    activateTab(group, firstTrigger, targetId);
  });
});