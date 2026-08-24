#!/bin/sh
# Noctis Minimus

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
put_template 0  "18/2a/35"
put_template 1  "c0/88/72"
put_template 2  "72/c0/9f"
put_template 3  "c8/a9/84"
put_template 4  "61/96/b8"
put_template 5  "c2/80/97"
put_template 6  "72/b7/c0"
put_template 7  "c5/cd/d3"
put_template 8  "42/58/66"
put_template 9  "ca/84/68"
put_template 10 "84/c8/ab"
put_template 11 "d1/aa/7b"
put_template 12 "68/a4/ca"
put_template 13 "c8/8d/a2"
put_template 14 "84/c0/c8"
put_template 15 "c5/d1/d3"

color_foreground="c5/cd/d3"
color_background="1b/29/32"

if [ -n "$ITERM_SESSION_ID" ]; then
  # iTerm2 proprietary escape codes
  put_template_custom Pg "c5cdd3"
  put_template_custom Ph "1b2932"
  put_template_custom Pi "c5cdd3"
  put_template_custom Pj "263c4a"
  put_template_custom Pk "c5cdd3"
  put_template_custom Pl "c5cdd3"
  put_template_custom Pm "1b2932"
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
