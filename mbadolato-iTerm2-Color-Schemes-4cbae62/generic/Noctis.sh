#!/bin/sh
# Noctis

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
put_template 0  "32/4a/4d"
put_template 1  "e6/65/33"
put_template 2  "49/e9/a6"
put_template 3  "e4/b7/81"
put_template 4  "49/ac/e9"
put_template 5  "df/76/9b"
put_template 6  "49/d6/e9"
put_template 7  "b2/ca/cd"
put_template 8  "47/68/6c"
put_template 9  "e9/77/49"
put_template 10 "60/eb/b1"
put_template 11 "e6/95/33"
put_template 12 "60/b6/eb"
put_template 13 "e7/98/b3"
put_template 14 "60/db/eb"
put_template 15 "c1/d4/d7"

color_foreground="b2/ca/cd"
color_background="05/25/29"

if [ -n "$ITERM_SESSION_ID" ]; then
  # iTerm2 proprietary escape codes
  put_template_custom Pg "b2cacd"
  put_template_custom Ph "052529"
  put_template_custom Pi "b2cacd"
  put_template_custom Pj "0f3a3f"
  put_template_custom Pk "b2cacd"
  put_template_custom Pl "b2cacd"
  put_template_custom Pm "052529"
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
