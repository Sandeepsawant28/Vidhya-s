// Vidya's Liquor Loft - Global App Controller (Theme, Motion, PWA, Toast)

// 1. Toast Notification System
window.toast = function (text) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = text;
    el.classList.add('on');
    clearTimeout(window.toastTimer);
    window.toastTimer = setTimeout(() => {
        el.classList.remove('on');
    }, 2400);
};

document.addEventListener('DOMContentLoaded', function () {
    // 2. Theme Toggle (Dark / Light)
    const themeBtn = document.getElementById('theme');
    const root = document.documentElement;

    function updateThemeUI(theme) {
        if (!themeBtn) return;
        const icon = themeBtn.querySelector('.tool-icon');
        const label = themeBtn.querySelector('.tool-label');
        if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
        if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
        else themeBtn.textContent = theme === 'dark' ? 'Light' : 'Dark';
    }

    const savedTheme = localStorage.getItem('vll_theme');
    if (savedTheme) {
        root.dataset.theme = savedTheme;
        updateThemeUI(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        updateThemeUI('dark');
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', function () {
            const isDark = root.dataset.theme === 'dark' || (!root.dataset.theme && window.matchMedia('(prefers-color-scheme: dark)').matches);
            const newTheme = isDark ? 'light' : 'dark';
            root.dataset.theme = newTheme;
            localStorage.setItem('vll_theme', newTheme);
            updateThemeUI(newTheme);
            window.toast(`Switched to ${newTheme} theme`);
        });
    }

    // 3. Motion Preference (Calm vs Animated)
    const motionBtn = document.getElementById('motion');
    function updateMotionUI(isCalm) {
        if (!motionBtn) return;
        const label = motionBtn.querySelector('.tool-label');
        if (label) label.textContent = isCalm ? 'Calm' : 'Motion';
        else motionBtn.textContent = isCalm ? 'Motion off' : 'Motion on';
    }

    const savedMotion = localStorage.getItem('vll_motion');
    if (savedMotion === 'calm') {
        root.classList.add('calm');
        updateMotionUI(true);
    }

    if (motionBtn) {
        motionBtn.addEventListener('click', function () {
            const isCalm = root.classList.toggle('calm');
            localStorage.setItem('vll_motion', isCalm ? 'calm' : 'normal');
            updateMotionUI(isCalm);
            window.toast(isCalm ? 'Animations disabled' : 'Animations enabled');
        });
    }

    // Sheet touch dismiss / swipe down
    const sheet = document.getElementById('sheet');
    if (sheet) {
        let startY = 0;
        sheet.addEventListener('touchstart', e => {
            startY = e.touches[0].clientY;
        }, { passive: true });
        sheet.addEventListener('touchmove', e => {
            const currentY = e.touches[0].clientY;
            if (currentY - startY > 60) {
                sheet.classList.remove('on');
            }
        }, { passive: true });
    }

    // 4. Register Progressive Web App (PWA) Offline Service Worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('Service Worker registered with scope:', reg.scope))
            .catch(err => console.log('Service Worker registration skipped or failed:', err));
    }

    // 5. SpecularButton Interactive Physics (Proximity: 250px, Idle: 0.35, Max: 1.0)
    const PROXIMITY_RADIUS = 250;
    const IDLE_INTENSITY = 0.35;
    const MAX_INTENSITY = 1.0;

    function getButtons() {
        return document.querySelectorAll('.specular-btn, .primary, .theme-btn');
    }

    window.addEventListener('mousemove', function (e) {
        const buttons = getButtons();
        buttons.forEach(btn => {
            const rect = btn.getBoundingClientRect();
            const relX = e.clientX - rect.left;
            const relY = e.clientY - rect.top;

            // Track mouse coords for the radial specular highlight
            btn.style.setProperty('--mouse-x', `${relX}px`);
            btn.style.setProperty('--mouse-y', `${relY}px`);

            // Proximity glow calculation
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const distance = Math.hypot(e.clientX - centerX, e.clientY - centerY);

            if (distance < PROXIMITY_RADIUS) {
                const proximityFactor = 1 - (distance / PROXIMITY_RADIUS);
                const dynamicIntensity = IDLE_INTENSITY + (proximityFactor * (MAX_INTENSITY - IDLE_INTENSITY));
                btn.style.setProperty('--intensity', dynamicIntensity.toFixed(2));
            } else {
                btn.style.setProperty('--intensity', IDLE_INTENSITY.toString());
            }
        });
    });

    // Touch support for mobile staff phones
    window.addEventListener('touchmove', function (e) {
        if (!e.touches.length) return;
        const touch = e.touches[0];
        const buttons = getButtons();
        buttons.forEach(btn => {
            const rect = btn.getBoundingClientRect();
            if (
                touch.clientX >= rect.left && touch.clientX <= rect.right &&
                touch.clientY >= rect.top && touch.clientY <= rect.bottom
            ) {
                btn.style.setProperty('--mouse-x', `${touch.clientX - rect.left}px`);
                btn.style.setProperty('--mouse-y', `${touch.clientY - rect.top}px`);
                btn.style.setProperty('--intensity', '1.0');
            } else {
                btn.style.setProperty('--intensity', IDLE_INTENSITY.toString());
            }
        });
    }, { passive: true });
});

