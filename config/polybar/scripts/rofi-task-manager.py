#!/usr/bin/env python3
import subprocess
import os

def get_lang():
    lang_file = os.path.expanduser("~/.config/dotfiles/language")
    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r") as f:
                return f.read().strip()
        except:
            pass
    return os.environ.get("LANG", "en").split("_")[0].split(".")[0]

def L(translations):
    lang = get_lang()
    if lang in translations:
        return translations[lang]
    if 'en' in translations:
        return translations['en']
    return list(translations.values())[0]

def main():
    try:
        user = os.environ.get("USER", "root")
        ps_output = subprocess.check_output(
            ["ps", "-u", user, "-o", "pid,rss,comm"],
            text=True
        )
    except Exception as e:
        return
    
    lines = ps_output.strip().split("\n")[1:]
    
    # Group processes by name
    groups = {}
    
    for line in lines:
        parts = line.strip().split(None, 2)
        if len(parts) == 3:
            pid, rss_kb, comm = parts
            try:
                rss_mb = int(rss_kb) / 1024
            except ValueError:
                rss_mb = 0
            
            # Avoid showing the task manager itself
            if "rofi" in comm.lower() or "awk" in comm.lower():
                continue
                
            if comm not in groups:
                groups[comm] = {"rss_mb": 0, "count": 0}
            groups[comm]["rss_mb"] += rss_mb
            groups[comm]["count"] += 1
            
    # Sort groups by total memory
    sorted_groups = sorted(groups.items(), key=lambda x: x[1]["rss_mb"], reverse=True)
    
    options = []
    comm_map = {}
    
    valid_groups = [(c, d["rss_mb"], d["count"]) for c, d in sorted_groups if d["rss_mb"] > 15.0]
    
    if valid_groups:
        # Calculate dynamic padding based on the longest active process name
        max_len = max(len(g[0]) for g in valid_groups)
        max_len = min(max_len, 25) # Cap at 25 chars
        
        for comm, mem_mb, count in valid_groups:
            name_padded = comm[:max_len].ljust(max_len)
            count_str = f"({count} proc)"
            entry = f"{name_padded}  |  {mem_mb:>6.1f} MB  |  {count_str}"
            options.append(entry)
            comm_map[entry] = comm
            
    if not options:
        options = ["No consuming processes found"]
    
    prompt = L({
        "es": "Administrador de Tareas",
        "en": "Task Manager",
        "pt": "Gerenciador de Tarefas",
        "fr": "Gestionnaire des tâches",
        "ru": "Диспетчер задач"
    })
    
    theme_str = 'window { width: 45%; } listview { lines: 12; } element-text { font: "JetBrainsMono Nerd Font Mono 11"; }'
    rofi_cmd = ["rofi", "-dmenu", "-p", prompt, "-i", "-theme-str", theme_str]
    
    rofi_proc = subprocess.run(rofi_cmd, input="\n".join(options), text=True, capture_output=True)
    if rofi_proc.returncode != 0:
        return # User cancelled
        
    choice = rofi_proc.stdout.strip()
    if choice not in comm_map:
        return
        
    comm = comm_map[choice]
    
    confirm_prompt = L({
        "es": f"¿Cerrar {comm}?",
        "en": f"Close {comm}?",
        "pt": f"Fechar {comm}?",
        "fr": f"Fermer {comm}?",
        "ru": f"Закрыть {comm}?"
    })
    
    yes_opt = L({"es": "Sí, forzar cierre", "en": "Yes, force close", "pt": "Sim, forçar fechamento", "fr": "Oui, forcer la fermeture", "ru": "Да, принудительно закрыть"})
    no_opt = L({"es": "No, cancelar", "en": "No, cancel", "pt": "Não, cancelar", "fr": "Non, annuler", "ru": "Нет, отмена"})
    
    confirm_theme = 'window { width: 450px; } listview { lines: 2; }'
    confirm_rofi = ["rofi", "-dmenu", "-p", confirm_prompt, "-i", "-theme-str", confirm_theme]
    confirm_proc = subprocess.run(confirm_rofi, input=f"{yes_opt}\n{no_opt}", text=True, capture_output=True)
    
    if confirm_proc.returncode != 0:
        return
        
    confirm_choice = confirm_proc.stdout.strip()
    if confirm_choice == yes_opt:
        subprocess.run(["pkill", "-u", user, "-x", comm])

if __name__ == "__main__":
    main()