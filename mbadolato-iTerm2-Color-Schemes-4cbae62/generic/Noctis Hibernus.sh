#!/bin/sh
# Noctis Hibernus

# source for these helper functions:
# https://github.com/chriskempson/base16-shell/blob/master/templates/default.mustache
if [ -n "$TMUX" ]; then
  # Tell tmux to pass the escape sequences through
  # (Source: http://permalink.gmane.org/gmane.comp.terminal-emulators.tmux.user/1324)
  put_template() { printf '\033Ptmux;\033\033]4;%d;rgb:%s\033\033\\\033\\' $@; }
  put_template_var() { printf '\033Ptmux;\033\033]%d;rgb:%s\033\033\\\033\\' $@; }
  put_template_custom() { printf '\033Ptmux;\033\033]%s%s\033\033\\\033\\' $@; }
elif [ "${TERM%%[-.]*}" = "screen" ]; then
  # GNU screen (screen, screen-256color, screen-256color-bce)
  put_template() { printf '\033P\033]4;%d;rgb:%s\007\033\\' $@; }
  put_template_var() { printf '\033P\033]%d;rgb:%s\007\033\\' $@; }
  put_template_custom() { printf '\033P\033]%s%s\007\033\\' $@; }
elif [ "${TERM%%-*}" = "linux" ]; then
  put_template() { [ $1 -lt 16 ] && printf "\e]P%x%s" $1 $(echo $2 | sed 's/\///g'); }
  put_template_var() { true; }
  put_template_custom() { true; }
else
  put_template() { printf '\033]4;%d;rgb:%s\033\\' $@; }
  put_template_var() { printf '\033]%d;rgb:%s\033\\' $@; }
  put_template_custom() { printf '\033]%s%s\033\\' $@; }
fi

# 16 color space
put_template 0  "00/3b/42"
put_template 1  "e3/4e/1c"
put_template 2  "00/b3/68"
put_template 3  "f4/97/25"
put_template 4  "00/94/f0"
put_template 5  "ff/57/92"
put_template 6  "00/bd/d6"
put_template 7  "8c/a6/a6"
put_template 8  "00/4d/57"
put_template 9  "ff/40/00"
put_template 10 "00/d1/7a"
put_template 11 "ff/8c/00"
put_template 12 "0f/a3/ff"
put_template 13 "ff/6b/9f"
put_template 14 "00/cb/e6"
put_template 15 "bb/c3/c4"

color_foreground="00/56/61"
color_background="f4/f6/f6"

if [ -n "$ITERM_SESSION_ID" ]; then
  # iTerm2 proprietary escape codes
  put_template_custom Pg "005661"
  put_template_custom Ph "f4f6f6"
  put_template_custom Pi "005661"
  put_template_custom Pj "d9e0e0"
  put_template_custom Pk "005661"
  put_template_custom Pl "005661"
  put_template_custom Pm "f4f6f6"
else
  put_template_var 10 $color_foreground
  put_template_var 11 $color_background
  if [ "${TERM%%-*}" = "rxvt" ]; then
    put_template_var 708 $color_background # internal border (rxvt)
  fi
  put_template_custom 12 ";7" # cursor (reverse video)
fi

# clean up
unset -f put_template
unset -f put_template_var
unset -f put_template_custom

unset color_foreground
unset color_background
