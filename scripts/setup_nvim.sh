#!/usr/bin/env bash

# Script para instalar y configurar Neovim
set -e

echo "--- Iniciando configuración ---"

# 1. Instalar dependencias
sudo apt update
sudo apt install -y git ripgrep fd-find build-essential default-jdk maven gradle curl nodejs npm

# 2. Asegurar versión reciente de Neovim
curl -LO https://github.com/neovim/neovim/releases/latest/download/nvim-linux-x86_64.appimage
chmod u+x nvim-linux-x86_64.appimage
sudo mv nvim-linux-x86_64.appimage /usr/local/bin/nvim

# 3. Preparar directorios
mkdir -p ~/.config/nvim/lua

# 3.5 Crear módulo de persistencia de tema
cat <<EOF > ~/.config/nvim/lua/theme_persist.lua
local M = {}
local theme_file = vim.fn.stdpath("config") .. "/current_theme.txt"
function M.save(theme)
    local file = io.open(theme_file, "w")
    if file then
        file:write(theme)
        file:close()
    end
end
function M.load()
    local file = io.open(theme_file, "r")
    if file then
        local theme = file:read("*all")
        file:close()
        return theme
    end
    return "catppuccin-mocha"
end
return M
EOF

# 4. Generar init.lua
cat <<EOF > ~/.config/nvim/init.lua
vim.g.mapleader = " "
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.mouse = 'a'
vim.opt.clipboard = 'unnamedplus'
vim.opt.fillchars = { eob = " " }
vim.opt.termguicolors = true

-- Función para aplicar transparencia agresiva
local function apply_transparency()
    local groups = {
        "Normal", "NormalNC", "NonText", "SignColumn", "EndOfBuffer",
        "NvimTreeNormal", "NvimTreeNormalNC", "NvimTreeEndOfBuffer",
        "NvimTreeWinSeparator", "NvimTreeVertSplit", "NvimTreeStatusLine",
        "NvimTreeStatusLineNC", "LineNr", "CursorLineNr", "StatusLine",
        "StatusLineNC", "WinSeparator", "VertSplit", "TelescopeNormal",
        "TelescopeBorder", "TelescopePromptBorder", "MsgArea"
    }
    for _, group in ipairs(groups) do
        vim.api.nvim_set_hl(0, group, { bg = "NONE", ctermbg = "NONE" })
    end
end

-- Persistencia de tema y re-aplicación de transparencia
local theme_persist = require('theme_persist')

vim.api.nvim_create_autocmd("ColorScheme", {
    callback = function()
        -- Guardar el nombre del tema
        local theme = vim.g.colors_name
        if theme then
            theme_persist.save(theme)
        end
        -- Re-aplicar transparencia después de cargar el tema
        apply_transparency()
    end
})

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({ "git", "clone", "--filter=blob:none", "https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({ 
  { "nvim-tree/nvim-tree.lua", version = "*", lazy = false, dependencies = { "nvim-tree/nvim-web-devicons" }, config = function() require("nvim-tree").setup {} vim.keymap.set("n", "<C-n>", ":NvimTreeToggle<CR>") end },
  { "sphamba/smear-cursor.nvim", opts = { cursor_color = "#ffffff" } },
  { "catppuccin/nvim", name = "catppuccin", priority = 1000, config = function()
      require("catppuccin").setup({ 
          transparent_background = true,
          integrations = {
              telescope = { enabled = true },
              bufferline = true,
              mason = true,
              nvimtree = true,
          }
      })
    end
  },
  { "akinsho/bufferline.nvim", version = "*", dependencies = 'nvim-tree/nvim-web-devicons', config = function() 
      require("bufferline").setup{ options = { offsets = {{ filetype = "NvimTree", text = "File Explorer", text_align = "left" }} } } 
    end 
  },
  { "folke/tokyonight.nvim", config = function() 
      require("tokyonight").setup({ 
          transparent = true,
          styles = {
              sidebars = "transparent",
              floats = "transparent",
          }
      }) 
    end 
  },
  { "ellisonleao/gruvbox.nvim" },
  { "Mofiqul/dracula.nvim", config = function() require("dracula").setup({ transparent_bg = true }) end },
  { "nvim-telescope/telescope.nvim", dependencies = { "nvim-lua/plenary.nvim" } },
  { "nvim-telescope/telescope-ui-select.nvim" },
  
  { "williamboman/mason.nvim", config = function() require("mason").setup() end },
  { "williamboman/mason-lspconfig.nvim", config = function() 
      require("mason-lspconfig").setup({ ensure_installed = { "pyright", "lua_ls", "ts_ls", "bashls", "cssls", "jdtls", "clangd" } })
    end 
  },
  { "neovim/nvim-lspconfig", config = function()
      local cap = require('cmp_nvim_lsp').default_capabilities()
      local servers = { "pyright", "lua_ls", "ts_ls", "bashls", "cssls", "jdtls", "clangd" }
      for _, name in ipairs(servers) do
        vim.lsp.config(name, { capabilities = cap })
        vim.lsp.enable(name)
      end
    end
  },
  { "hrsh7th/cmp-nvim-lsp" },
  { "hrsh7th/nvim-cmp", config = function()
      local cmp = require('cmp')
      cmp.setup({
        mapping = cmp.mapping.preset.insert({ ['<C-Space>'] = cmp.mapping.complete(), ['<CR>'] = cmp.mapping.confirm({ select = true }) }),
        sources = cmp.config.sources({ { name = 'nvim_lsp' } })
      })
    end
  }
})

-- Cargar el tema guardado
pcall(vim.cmd.colorscheme, theme_persist.load())

-- Re-aplicar transparencia al final para asegurar
apply_transparency()

vim.keymap.set('n', '<leader>th', ':Telescope colorscheme<CR>', { desc = "Selector de temas" })

-- Atajos para BufferLine
vim.keymap.set('n', '<A-h>', ':BufferLineCyclePrev<CR>', { desc = "Pestaña anterior" })
vim.keymap.set('n', '<A-l>', ':BufferLineCycleNext<CR>', { desc = "Pestaña siguiente" })
vim.keymap.set('n', '<A-w>', ':bdelete<CR>', { desc = "Cerrar pestaña" })

for i = 1, 9 do
  vim.keymap.set('n', '<A-' .. i .. '>', ':BufferLineGoToBuffer ' .. i .. '<CR>')
end
EOF

echo "--- Configuración completada ---"
