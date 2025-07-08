class Toast {
    constructor() {
        this.container = document.querySelector('.toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    }

    show(message, type = 'error', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = document.createElement('span');
        icon.innerHTML = type === 'error' 
            ? '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
            : '<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
        
        const text = document.createElement('span');
        text.textContent = message;
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
        closeBtn.onclick = () => this.close(toast);
        
        toast.appendChild(icon);
        toast.appendChild(text);
        toast.appendChild(closeBtn);
        
        this.container.appendChild(toast);
        
        if (duration > 0) {
            setTimeout(() => this.close(toast), duration);
        }
        
        return toast;
    }
    
    close(toast) {
        if (!toast.classList.contains('removing')) {
            toast.classList.add('removing');
            toast.addEventListener('animationend', () => {
                toast.remove();
                if (this.container.children.length === 0) {
                    this.container.remove();
                }
            });
        }
    }
}

// Create global toast instance
window.toast = new Toast(); 