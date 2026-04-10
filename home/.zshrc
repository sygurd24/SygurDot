# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
# Dotfiles Localización
[[ -f ~/.config/dotfiles/locale.sh ]] && source ~/.config/dotfiles/locale.sh

# Powerlevel10k Theme
source ~/.zsh/powerlevel10k/powerlevel10k.zsh-theme

# History Configuration
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt APPEND_HISTORY
setopt SHARE_HISTORY
setopt INC_APPEND_HISTORY

# Basic Options
setopt AUTO_CD
setopt CORRECT

# Ensure SHELL variable reflects Zsh
export SHELL=/usr/bin/zsh

# Plugins
source ~/.zsh/zsh-autosuggestions/zsh-autosuggestions.zsh
source ~/.zsh/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# Aliases
alias ll='lsd -alF'
alias la='lsd -A'
alias l='lsd -CF'
alias ls='lsd'
alias cat='batcat'
alias bat='batcat'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'

# Load Powerlevel10k configuration
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Fetch Tool
alias fetch='fastfetch --config ~/.config/fastfetch/config.jsonc'

# Flutter SDK
export PATH="$PATH:$HOME/development/flutter/bin:$HOME/.local/bin"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
