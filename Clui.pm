# Term::Clui.pm
#########################################################################
#        This Perl module is Copyright (c) 2002, Peter J Billam         #
#               c/o P J B Computing, www.pjb.com.au                     #
#                                                                       #
#     This module is free software; you can redistribute it and/or      #
#            modify it under the same terms as Perl itself.             #
#########################################################################

package Term::Clui;
$VERSION = '1.22';
my $stupid_bloody_warning = $VERSION;  # circumvent -w warning
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(ask_password ask confirm choose edit sorry view inform);
@EXPORT_OK = qw(beep tiview back_up get_default set_default timestamp);

no strict; local $^W = 0;

# ------------------------ vt100 stuff -------------------------

$A_NORMAL    =  0;
$A_BOLD      =  1;
$A_UNDERLINE =  2;
$A_REVERSE   =  4;
$KEY_UP    = oct(403);
$KEY_LEFT  = oct(404);
$KEY_RIGHT = oct(405);
$KEY_DOWN  = oct(402);
$KEY_ENTER = "\r";
$KEY_ENTER .= '';  # circumvent stupid bloody -w warning
$KEY_PPAGE = oct(523);
$KEY_NPAGE = oct(522);
$KEY_BTAB  = oct(541);

# $bsd = (-f "/kernel" || -f "/vmunix" || -f "/386bsd");

my $irow; my $icol;   # maintained by &puts, &up, &down, &left and &right
sub puts   { my $s = join '', @_;
	$irow += ($s =~ tr/\n/\n/);
	if ($s =~ /\r$/) { $icol = 0; }   # should increment otherwise ...
	print TTY $s;
}
# could terminfo sgr0, bold, rev, cub1, cuu1, cuf1, cud1 ...
sub attrset { my $attr = $_[$[];
	if (! $attr) {
		print TTY "\033[0m";
	} else {
		if ($attr & $A_BOLD)      { print TTY "\033[1m" };
		if ($attr & $A_REVERSE)   { print TTY "\033[7m" };
		if ($attr & $A_UNDERLINE) { print TTY "\033[4m" };
	}
}
sub beep     { print TTY "\07"; }
sub clear    { print TTY "\033[H\033[J"; }
sub clrtoeol { print TTY "\033[K"; }
sub black    { print TTY "\033[30m"; }
sub red      { print TTY "\033[31m"; }
sub green    { print TTY "\033[32m"; }
sub blue     { print TTY "\033[34m"; }
sub violet   { print TTY "\033[35m"; }
my ($rin, $nfound, $timeleft);  # for use by select
sub getch {
	my $c = getc(TTYIN);
	if ($c eq "\033") {
		#($nfound, $timeleft)= select($rout=$rin, undef, undef, 0.05);
		# warn "nfound=$nfound\n";  # always 0 on FreeBSD's cons25l1 :-(
		#if (! $nfound) {return "\033"; }
		$c = getc(TTYIN);
		if ($c eq "A") { return($KEY_UP); }
		if ($c eq "B") { return($KEY_DOWN); }
		if ($c eq "C") { return($KEY_RIGHT); }
		if ($c eq "D") { return($KEY_LEFT); }
		if ($c eq "5") { getc(TTYIN); return($KEY_PPAGE); }
		if ($c eq "6") { getc(TTYIN); return($KEY_NPAGE); }
		if ($c eq "Z") { return($KEY_BTAB); }
		if ($c eq "[") {
			$c = getc(TTYIN);
			if ($c eq "A") { return($KEY_UP); }
			if ($c eq "B") { return($KEY_DOWN); }
			if ($c eq "C") { return($KEY_RIGHT); }
			if ($c eq "D") { return($KEY_LEFT); }
			if ($c eq "5") { getc(TTYIN); return($KEY_PPAGE); }
			if ($c eq "6") { getc(TTYIN); return($KEY_NPAGE); }
			if ($c eq "Z") { return($KEY_BTAB); }
			return($c);
		}
		return($c);
	} elsif ($c == oct(0217)) {
		$c = getc(TTYIN);
		if ($c eq "A") { return($KEY_UP); }
		if ($c eq "B") { return($KEY_DOWN); }
		if ($c eq "C") { return($KEY_RIGHT); }
		if ($c eq "D") { return($KEY_LEFT); }
		return($c);
	} elsif ($c == oct(0233)) {
		$c = getc(TTYIN);
		if ($c eq "A") { return($KEY_UP); }
		if ($c eq "B") { return($KEY_DOWN); }
		if ($c eq "C") { return($KEY_RIGHT); }
		if ($c eq "D") { return($KEY_LEFT); }
		if ($c eq "5") { getc(TTYIN); return($KEY_PPAGE); }
		if ($c eq "6") { getc(TTYIN); return($KEY_NPAGE); }
		if ($c eq "Z") { return($KEY_BTAB); }
		return($c);
	} else {
		return($c);
	}
}
sub up    {
	if ($_[$[] < 0) { &down($_[$[]); return; }
	print TTY "\033[A" x $_[$[]; $irow -= $_[$[];
}
sub down  {
	if ($_[$[] < 0) { &up($_[$[]); return; }
	print TTY "\n" x $_[$[]; $irow += $_[$[];
}
sub right {
	if ($_[$[] < 0) { &up($_[$[]); return; }
	print TTY "\033[C" x $_[$[]; $icol += $_[$[];
}
sub left  {
	if ($_[$[] < 0) { &up($_[$[]); return; }
	print TTY "\033[D" x $_[$[]; $icol -= $_[$[];
}
sub goto { my $newcol = shift; my $newrow = shift;
	if ($newcol == 0) { print TTY "\r" ; $icol = 0;
	} elsif ($newcol > $icol) { &right($newcol-$icol);
	} elsif ($newcol < $icol) { &left ($icol-$newcol);
	}
	if ($newrow > $irow)      { &down ($newrow-$irow);
	} elsif ($newrow < $irow) { &up   ($irow-$newrow);
	}
}
sub move { my ($ix,$iy) = @_; printf TTY "\033[%d;%dH",$iy+1,$ix+1; }
my $initscr_already_run = 0; my $stty = '';
sub initscr {
	if ($initscr_already_run) {
		$icol = 0; $irow = 0; $initscr_already_run++; return;
	}
	open(TTY, ">/dev/tty")  || (warn "Can't write /dev/tty: $!\n", return 0);
	$stty = `stty -g`; chop $stty;
	open(TTYIN, "</dev/tty") || (warn "Can't read /dev/tty: $!\n", return 0);

	if ($^O =~ /^FreeBSD$/i) { system("stty -echo -icrnl raw </dev/tty");
	} else { system("stty -echo -icrnl raw </dev/tty >/dev/tty");
	}
	# system("stty -echo -icrnl raw </dev/tty");  # various old tries ...
	# system("stty -echo -icrnl raw");
	# if ($bsd) { system "stty cbreak </dev/tty >/dev/tty 2>&1";
	# } else { system "stty", '-icanon'; system "stty", 'eol', "\001";
	# }

	select((select(TTY), $| = 1)[$[]); print TTY "";
	$rin = ''; vec($rin, fileno(TTYIN), 1) = 1;
	$icol = 0; $irow = 0; $initscr_already_run = 1;
}
sub endwin {
	print TTY "\033[0m";
	if ($initscr_already_run > 1) { $initscr_already_run--; return; }
	close TTY; close TTYIN;
	if ($^O =~ /^FreeBSD$/i) { system("stty $stty </dev/tty") if $stty;
	} else { system("stty $stty </dev/tty >/dev/tty") if $stty;
	}
	$initscr_already_run = 0;
}

# ----------------------- size handling ----------------------

my ($must_use_tput, $maxcols, $maxrows); my $size_changed = 1;

eval 'require "Term/Size.pm"';
if ($@) { $must_use_tput = 1; }

sub check_size {
	if (! $size_changed) { return; }
	if ($must_use_tput) {
		$maxcols = `tput cols`;
		if ($^O eq 'linux') { $maxrows = (`tput lines` + 0);
		} else { $maxrows = (`tput rows` + 0);
		}
	} else {
		($maxcols, $maxrows) = &Term::Size::chars(*STDERR);
	}
	$maxcols = $maxcols || 80; $maxcols--;
	$maxrows = $maxrows || 24;
	$size_changed = 0;
}
$SIG{'WINCH'} = sub { $size_changed = 1; };

# ------------------------ ask stuff -------------------------

# Options such as integer, real, positive, >x, >=x, <x <=x,
# non-null, max-length, min-length, silent  ...
# default could be just one more option, and backward compatibilty
# could be preserved by checking whether the 2nd arg is a hashref ...

sub ask_password { # no echo - use for passwords
	local ($silent) = 'yes'; &ask ($_[$[]);
}
sub ask { my ($question, $default) = @_;
	return '' unless $question;
	&initscr(); my $nol = &display_question($question);

   my $i = 0; my $n = 0; my @s = (); # cursor position, length, string
	if ($default) {
		$default =~ s/\t/	/g;
		@s = split ('', $default); $n = scalar @s; $i = $[;
		foreach $j ($[ .. $n) { &puts($s[$j]); }
		&left($n);
	}

	while (1) {
		$c = &getch();
		if ($c eq "\r") { &erase_lines(1); last; }
		if ($size_changed) {
			&erase_lines(0); $nol = &display_question($question);
		}
		if ($c == $KEY_LEFT && $i > 0) { $i--; &left(1);
		} elsif ($c == $KEY_RIGHT) {
			if ($i < $n) { &puts ($silent ? "x" : $s[$i]); $i++; }
		} elsif (($c eq "\cH") || ($c eq "\c?")) {
			if ($i > 0) {
			 	$n--; $i--; splice(@s, $i, 1); &left(1);
			  	foreach $j ($i .. $n) { &puts($s[$j]); }
			  	&clrtoeol(); &left($n-$i);
			}
		} elsif ($c eq "\cC" || $c eq "\cX" || $c eq "\cD") {  # clear ...
			&left($i); $i = 0; $n = 0; @s = (); &clrtoeol();
		} elsif ($c eq "\cB") { &left($i); $i = 0;
		} elsif ($c eq "\cE") { &right($n-$i); $i = $n;
		} elsif ($c eq "\cL") {  # redraw ...
		} elsif ($c > 255) { &beep();
		} elsif ($c =~ /^[\040-\376]$/) {
			splice(@s, $i, 0, $c);
			$n++; $i++; &puts($silent ? "x" : $c);
			foreach $j ($i .. $n) { &puts($s[$j]); }
			&clrtoeol();  &left($n-$i);
		} else { &beep();
		}
	}
	&endwin(); $silent = ''; return join("", @s);
}

# ----------------------- choose stuff -------------------------
sub debug {
	if (! open (DEBUG, '>>/tmp/clui.log')) {
		warn "can't open /tmp/clui.log: $!\n"; return;
	}
	print DEBUG "$_[$[]\n"; close DEBUG;
}

my (%irow, %icol, $nrows, $clue_has_been_given, $choice, $this_cell);
my @marked;
my $HOME = $ENV{'HOME'} || $ENV{'LOGDIR'} || (getpwuid($<))[7];
srand(time() ^ ($$+($$<15)));

sub choose {  local ($question, @list) = @_;  # @list must be local
	# As from 1.22, allows multiple choice if called in array context

	return unless @list;
	grep (($_ =~ s/\n$//) && 0, @list);	# chop final \n if any
	my @biglist = @list; my $icell; @marked = ();

	$question =~ s/^[\n\r]+//;   # strip initial newline(s)
	$question =~ s/[\n\r]+$//;   # strip final newline(s)
	my ($firstline,$otherlines) = split ("\n", $question, 2);
	my $firstlinelength = length $firstline;

	$choice = &get_default($firstline);
	# If wantarray ? Is remembering multiple choices safe ?

	&initscr();
	&size_and_layout(0);
	if (wantarray) {
		$#marked = $#list;
		if ($firstlinelength < $maxcols-30) {
			&puts("$firstline (multiple choice with spacebar)\r\n");
		} elsif ($firstlinelength < $maxcols-16) {
			&puts("$firstline (multiple choice)\r\n");
		} elsif ($firstlinelength < $maxcols-9) {
			&puts("$firstline (multiple)\r\n");
		} else {
			&puts("$firstline\r\n");
		}
	} else {
		&puts("$firstline\r\n");
	}
	if ($nrows >= $maxrows) { @list = &narrow_the_search(@list); }
	&wr_screen();

	while (1) {
		$c = &getch();
		if ($size_changed) {
			&size_and_layout($nrows);
			if ($nrows >= $maxrows) { @list = &narrow_the_search(@list); }
			&wr_screen();
		}
		if ($c eq "q" || $c eq "\cD") {
			&erase_lines(1);
			if ($clue_has_been_given) {
				my $re_clue = &confirm("Do you want to change your clue ?");
				&up(1); &clrtoeol();   # erase the confirm
				if ($re_clue) {
					$irow = 1;
					@list = &narrow_the_search(@biglist); &wr_screen(); next;
				} else {
					&up(1); &clrtoeol(); &endwin (); $clue_has_been_given = 0;
         		return wantarray ? () : undef;
				}
			}
			&goto (0,0); &clrtoeol(); &endwin (); $clue_has_been_given = 0;
			return wantarray ? () : undef;
		} elsif (($c eq "\t") && ($this_cell < $#list)) {
			$this_cell++; &wr_cell($this_cell-1);
			&wr_cell($this_cell); 
		} elsif ((($c eq "l") || ($c eq $KEY_RIGHT)) && ($this_cell < $#list)
			&& ($irow[$this_cell] == $irow[$this_cell+1])) {
			$this_cell++; &wr_cell($this_cell-1);
			&wr_cell($this_cell); 
		} elsif ((($c eq "\cH") || ($c eq $KEY_BTAB)) && ($this_cell > $[)) {
			$this_cell--; &wr_cell($this_cell+1);
			&wr_cell($this_cell); 
		} elsif ((($c eq "h") || ($c eq $KEY_LEFT)) && ($this_cell > $[)
			&& ($irow[$this_cell] == $irow[$this_cell-1])) {
			$this_cell--; &wr_cell($this_cell+1);
			&wr_cell($this_cell); 
		} elsif ((($c eq "j") || ($c eq $KEY_DOWN)) && ($irow < $nrows)) {
			$mid_col = $icol[$this_cell] + 0.5 * $l[$this_cell];
			$left_of_target = 1000;
			for ($inew=$this_cell+1; $inew < $#list; $inew++) {
				last if $icol[$inew] < $mid_col;	# skip rest of row
			}
			for (; $inew < $#list; $inew++) {
				$new_mid_col = $icol[$inew] + 0.5 * $l[$inew];
				last if $new_mid_col >= $mid_col;		# we've reached it
				last if $icol[$inew+1] <= $icol[$inew]; # we're at EOL
				$left_of_target = $mid_col - $new_mid_col;
			}
			if (($new_mid_col - $mid_col) > $left_of_target) { $inew--; }
			$iold = $this_cell; $this_cell = $inew;
			&wr_cell($iold); &wr_cell($this_cell);
		} elsif ((($c eq "k") || ($c eq $KEY_UP)) && ($irow > 1)) {
			$mid_col = $icol[$this_cell] + 0.5 * $l[$this_cell];
			$right_of_target = 1000;
			for ($inew=$this_cell-1; $inew > 0; $inew--) {
				last if $irow[$inew] < $irow[$this_cell];	# skip rest of row
			}
			for (; $inew > 0; $inew--) {
				last unless $icol[$inew];
				$new_mid_col = $icol[$inew] + 0.5 * $l[$inew];
				last if $new_mid_col < $mid_col;		 # we're past it
				$right_of_target = $new_mid_col - $mid_col;
			}
			if (($mid_col - $new_mid_col) > $right_of_target) { $inew++; }
			$iold = $this_cell; $this_cell = $inew;
			&wr_cell($iold); &wr_cell($this_cell);
		} elsif ($c eq "\cL") {
			if ($size_changed) {
				&size_and_layout($nrows);
				if ($nrows >= $maxrows) { @list = &narrow_the_search(@list); }
			}
			&wr_screen();
		} elsif ($c eq "\r") {
			&erase_lines(1); &goto($firstlinelength+1, 0);
			my @chosen;
			if (wantarray) {
				my $i; for ($i=$[; $i<=$#list; $i++) {
					if ($marked[$i] || $i==$this_cell) { push @chosen, $list[$i]; }
				}
				&clrtoeol();
				my $remaining = $maxcols-$firstlinelength;
				my $last = pop @chosen;
				my $dotsprinted;
				foreach (@chosen) {
					if (($remaining - length $_) < 4) {
						$dotsprinted=1; &puts("..."); $remaining -= 3; last;
					} else {
						&puts("$_, "); $remaining -= (2 + length $_);
					}
				}
				if (!$dotsprinted) {
					if (($remaining - length $last)>0) { &puts($last);
					} elsif ($remaining > 2) { &puts('...');
					}
				}
				&puts("\n\r");
				push @chosen, $last;
			} else {
				&puts($list[$this_cell]."\n\r");
			}
			&endwin();
			&set_default($firstline, $list[$this_cell]); # join ($,,@chosen) ?
			$clue_has_been_given = 0;
			if (wantarray) { return @chosen;
			} else { return $list[$this_cell];
			}
		} elsif ($c eq " ") {
			if (wantarray) {
				$marked[$this_cell] = !$marked[$this_cell];
				if ($this_cell < $#list) {
					$this_cell++; &wr_cell($this_cell-1); &wr_cell($this_cell); 
				}
			} elsif ($this_cell < $#list) {
				$this_cell++; &wr_cell($this_cell-1); &wr_cell($this_cell); 
			}
		}
	}
	warn "choose: shouldn't reach here ...\n";
	&endwin ();
}
sub layout { my @list = @_;
	$this_cell = 0; my $irow = 1; my $icol = 0;  my $i;
	for ($i=$[; $i<=$#list; $i++) {
		$l[$i] = length ($list[$i]) + 2;
		if (($icol + $l[$i]) >= $maxcols ) { $irow++; $icol = 0; }
		if ($irow > $maxrows) { return $irow; }  # save time
		$irow[$i] = $irow; $icol[$i] = $icol;
		$icol += $l[$i];
		if ($list[$i] eq $choice) { $this_cell = $i; }
	}
	return $irow;
}
sub wr_screen {
	my $i;
	for ($i=$[; $i<=$#list; $i++) {
		&wr_cell($i, $this_cell) unless $i==$this_cell;
	}
	&wr_cell($this_cell);
}
sub wr_cell { my $i = shift;
	&goto ($icol[$i], $irow[$i]);
	if ($marked[$i]) { &attrset($A_BOLD); }
	if ($i == $this_cell) { &attrset($A_REVERSE); }
	my $no_tabs = $list[$i];
	$no_tabs =~ s/\t/ /;
	$no_tabs =~ s/^(.{1,77}).*/$1/;
	&puts(" $no_tabs ");
	if ($marked[$i] || $i == $this_cell) { &attrset($A_NORMAL); }
	$icol += length ($no_tabs) + 2;
}
sub size_and_layout {
	my $erase_rows = shift;
	my $oldmaxrows = $maxrows;
	&check_size();
	if ($erase_rows) {
		if ($erase_rows > $maxrows) { $erase_rows = $maxrows; } # XXX?
		&erase_lines(1);
	}
	$nrows = &layout(@list);
}
sub narrow_the_search { my @biglist = @_;
	# replaces the old ... require 'complete.pl';
	# return &Complete("$firstline (TAB to complete, ^D to list) ", @list);
	my $nchoices = scalar @_;
	my $n; my $i; my @s; my $s; my @list = @biglist;
	$clue_has_been_given = 1;
	&ask_for_clue($nchoices, $i, $s);
	while (1) {
		$c = &getch();
		if ($size_changed) {
			&size_and_layout(0);
			if ($nrows < $maxrows) { &erase_lines(1); return @list; }
		}
		if ($c == $KEY_LEFT && $i > 0) { $i--; &left(1); next;
		} elsif ($c == $KEY_RIGHT) { if ($i < $n) { &puts($s[$i]); $i++; next; }
		} elsif (($c eq "\cH") || ($c eq "\c?")) {
			if ($i > 0) {
			 	$n--; $i--; splice(@s, $i, 1); &left(1);
			  	foreach $j ($i..$n) { &puts($s[$j]); } &clrtoeol(); &left($n-$i);
			}
		} elsif ($c eq "\cC" || $c eq "\cX" || $c eq "\cD") {  # clear ...
			&left($i); $i = 0; $n = 0; @s = (); &clrtoeol();
		} elsif ($c eq "\cB") { &left($i); $i = 0; next;
		} elsif ($c eq "\cE") { &right($n-$i); $i = $n; next;
		} elsif ($c eq "\cL") {

		} elsif ($c > 255) { &beep();
		} elsif ($nchoices && $c =~ /^[\040-\376]$/) {
			splice(@s, $i, 0, $c);
			$n++; $i++; &puts($c);
			foreach $j ($i..$n) { &puts($s[$j]); } &clrtoeol();  &left($n-$i);
		} else { &beep();
		}
		# grep, and if $nchoices=1 return
		$s = join("", @s);
		@list = grep($[ <= index($_,$s), @biglist);
		$nchoices = scalar @list;
		$nrows = &layout(@list);
		if ($nchoices==1 || ($nchoices && ($nrows<$maxrows))) {
			&puts("\r"); &clrtoeol(); &up(1); &clrtoeol(); return @list;
		}
		&ask_for_clue($nchoices, $i, $s);
	}
	warn "narrow_the_search: shouldn't reach here ...\n";
}
sub ask_for_clue { my ($nchoices, $i, $s) = @_;
	my $headstr; my $tailstr;
	if ($nchoices) {
		if ($s) {
			$headstr = "the choices won't fit; there are still";
			$tailstr = "of them";
			&goto(0,1); &puts("$headstr $nchoices $tailstr"); &clrtoeol();
			&goto(0,2); &puts("lengthen the clue : "); &right($i);
		} else {
			$headstr = "the choices won't fit; there are";
			$tailstr = "of them";
			&goto(0,1); &puts("$headstr $nchoices $tailstr"); &clrtoeol();
			&goto(0,2); &puts("   give me a clue : "); &right($i);
		}
	} else {
		&goto(0,1); &puts("No choices fit this clue !"); &clrtoeol();
		&goto(0,2); &puts(" shorten the clue : "); &right($i);
	}
}
sub get_default { my ($question) = @_;
	if ($ENV{CLUI_DIR} eq 'OFF') { return undef; }
	if (! $question) { return undef; }
	my @choices;
	my $n_tries = 5;
	while ($n_tries--) {
		if (dbmopen (%CHOICES, &dbm_file(), 0600)) {
			last;
		} else { 
			if ($! eq 'Resource temporarily unavailable') {
				my $wait = rand 0.45; select undef, undef, undef, $wait;
			} else { return undef;
			}
		}
	}
	@choices = split ($; ,$CHOICES{$question}); dbmclose %CHOICES;
	if (wantarray) { return @choices;
	} else { return $choices[$[];
	}
}
sub set_default { my $question = shift; my $s = join ($; , @_);
	if ($ENV{CLUI_DIR} eq 'OFF') { return undef; }
	if (! $question) { return undef; }
	my $n_tries = 5;
	while ($n_tries--) {
		if (dbmopen (%CHOICES, &dbm_file(), 0600)) {
			last;
		} else { 
			if ($! eq 'Resource temporarily unavailable') {
				my $wait = rand 0.50; select undef, undef, undef, $wait;
			} else { return undef;
			}
		}
	}
	$CHOICES{$question} = $s; dbmclose %CHOICES;
	return $s;
}
sub dbm_file {
	if ($ENV{CLUI_DIR} eq 'OFF') { return undef; }
	my $db_dir;
	if ($ENV{CLUI_DIR}) {
		$db_dir = $ENV{CLUI_DIR};
		$db_dir =~ s#^~/#$HOME/#;
	} else { $db_dir = "$HOME/.clui_dir";
	}
	mkdir ($db_dir,0750);
	return "$db_dir/choices";
}

# ----------------------- confirm stuff -------------------------

sub confirm { my $question = shift;  # asks user Yes|No, returns 1|0
	return(0) unless $question;  return(0) unless -t STDERR;
	&initscr();
	my $nol = &display_question($question); &puts (" (y/n) ");
	while (1) { $response=&getch();  last if ($response=~/[yYnN]/);  &beep(); }
	&left(6); &clrtoeol(); 
	if ($response=~/^[yY]/) { &puts("Yes"); } else { &puts("No"); }
	&erase_lines(1); &endwin();
	if ($response =~ /^[yY]/) { return 1; } else { return 0 ; }
}

# ----------------------- edit stuff -------------------------

sub edit {	my ($title, $text) = @_;
	my $argc = $#_ - $[ +1;
	my ($dirname, $basename, $rcsdir, $rcsfile, $rcs_ok);
	
	if ($argc == 0) {	# start editor session with no preloaded file
		system $ENV{EDITOR} || "vi"; # should also look in ~/db/choices.db
	} elsif ($argc == 2) {
		# must create tmp file with title embedded in name
		$tmpdir = '/tmp';
		($safename = $title) =~ s/[\W_]+/_/g;
		$file = "$tmpdir/$safename.$$";
		if (!open (F,"> $file")) {&sorry("can't open $file: $!\n");return '';}
		print F $text; close F;
		$editor = $ENV{EDITOR} || "vi"; # should also look in ~/db/choices.db
		system "$editor $file";
		if (!open (F,"< $file")) {&sorry ("can't open $file: $!\n");return 0;}
		undef $/; $text = <F>; $/ = "\n";
		close F; unlink $file; return $text;
	} elsif ($argc == 1) {	# its a file, we will try RCS ...
		my $file = $title;

		# weed out no-go situations
		if (-d $file)  { &sorry ("$file is already a directory\n"); return 0; }
		if (-B _ && -s _)  { &sorry("$file is not a text file\n");  return 0; }
		if (-T _ && !-w _) { &view ($file); return 1; }
	
		# it's a writeable text file, so work out the locations
		if ($file =~ /\//) {
			($dirname, $basename) = $file =~ /^(.*)\/([^\/]+)$/;
			$rcsdir  = "$dirname/RCS";
			$rcsfile = "$rcsdir/$basename,v";
		} else {
			$basename = $file;
			$rcsdir  = "RCS";
			$rcsfile = "$rcsdir/$basename,v";
		}
		$rcslog = "$rcsdir/log";
	
		# we no longer create the RCS directory if it doesn't exist,
		# so `mkdir RCS' to enable rcs in a directory ...
		$rcs_ok = 1;	if (!-d $rcsdir) { $rcs_ok = 0; }
		if (-d _ && ! -w _) { $rcs_ok = 0;	warn "can't write in $rcsdir\n"; }
	
		# if the file doesn't exist, but the RCS does, then check it out
		if ($rcs_ok && -f $rcsfile && !-f $file) {system "co -l $file $rcsfile";}

		my $starttime = time;
		$editor = $ENV{EDITOR} || "vi"; # should also look in ~/db/choices.db
		system "$editor $file";
		my $elapsedtime = time - $starttime;
		# could be output or logged, for worktime accounting
	
		if ($rcs_ok && -T $file) {	 # check it in
			if (!-f $rcsfile) {
				my $msg = &ask ("$file is new. Please describe it:");
				my $quotedmsg = $msg;  $quotedmsg =~ s/'/'"'"'/g;
				if ($msg) {
					system "rcs -i -U -t-'$quotedmsg' $file $rcsfile";
					&logit ($basename, $msg);
				}
			} else {
				my $msg = &ask ("What changes have you made to $file ?");
				my $quotedmsg = $msg;  $quotedmsg =~ s/'/'"'"'/g;
				if ($msg) {
					system "ci -q -l -m'$quotedmsg' $file $rcsfile";
					&logit ($basename, $msg);
				}
			}
		}
	}
}
sub logit { my ($file, $msg) = @_;
	if (! open (LOG, ">> $rcslog")) {  warn "can't open $rcslog: $!\n";
	} else {
		$pid = fork;	# log in background for better response time
		if (! $pid) {
			($user) = getpwuid ($>);
			print LOG &timestamp, " $file $user $msg\n"; close LOG;
			if ($pid == 0) { exit 0; }	# the child's end, if a fork occurred
		}
	}
}
sub timestamp {
   # returns current date and time in "199403011 113520" format
   my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime;
	$wday += 0; $yday += 0; $isdst += 0; # avoid bloody -w warning
   return sprintf ("%4.4d%2.2d%2.2d %2.2d%2.2d%2.2d",
      $year+1900, $mon+1, $mday, $hour, $min, $sec);
}

# ----------------------- sorry stuff -------------------------

sub sorry { # warns user of an error condition
	print STDERR "Sorry, $_[$[]\n";
}

sub inform { my $text = $_[$[];
	$text =~ s/([^\n])$/$1\n/s;
	if (open(TTY, ">/dev/tty")) { print TTY $text; close TTY;
	} else { warn $text;
	}
}

# ----------------------- view stuff -------------------------

foreach $f ("/usr/bin/less", "/usr/bin/more") {
	if (-x $f) { $default_pager = $f; }
}
sub view {	my ($title, $text) = @_;	# or ($filename) =
	if (! $text && -T $title && open(F,"< $title")) {
		$nlines = 0;
		while (<F>) { last if ($nlines++ > $maxrows); } close F;
		if ($nlines > (0.6*$maxrows)) {
			system (($ENV{PAGER} || $default_pager) . " \'$title\'");
		} else {
			open (F,"< $title"); undef $/; $text=<F>; $/="\n"; close F;
			&tiview($title, $text);
		}
	} else {
		local (@lines) = split (/\r?\n/, $text, $maxrows);
		if (($#lines - $[) < 21) {
			&tiview ($title, $text);
		} else {
			local ($safetitle); ($safetitle = $title) =~ s/[^a-zA-Z0-9]+/_/g;
			local ($tmp) = "/tmp/$safetitle.$$";
			if (! open (TMP, "> $tmp")) { warn "can't open $tmp: $!\n"; return; }
			print TMP $text;	close TMP;
			system (($ENV{PAGER} || $default_pager) . " \'$tmp\'");
			unlink $tmp;
			return 1;
		}
	}
}
sub tiview {	my ($title, $text) = @_;
	return unless $text; local ($[) = 0;
	$title =~ s/\t/ /g; my $titlelength = length $title;
	
	&check_size();
	my @rows = &fmt($text, nofill=>1);
	&initscr();
	if (3 > scalar @rows) {
		&puts(join("\r\n",@rows), "\r\n"); &endwin(); return 1;
	}
	if ($titlelength > ($maxcols-35)) { &puts ("$title\r\n");
	} else { &puts ("$title   (<enter> to continue, q to clear)\r\n");
	}
	&puts("\r", join("\e[K\r\n",@rows), "\r");
	$icol = 0; $irow = scalar @rows; &goto ($titlelength+1, 0);
	
	while (1) {
		$c = &getch();
		if ($c eq 'q' || $c eq "\cX" || $c eq "\cW" || $c eq "\cZ"
		|| $c eq "\cC" || $c eq "\c\\") {
			&erase_lines(0); &endwin(); return 1;
		} elsif ($c eq "\r") {  # <enter> retains text on screen
			&clrtoeol(); &goto (0, @rows+1); &endwin(); return 1;
		} elsif ($c eq "\cL") {
			&puts("\r"); &endwin(); &tiview($title,$text); return 1;
		}
	}
	warn "tiview: shouldn't reach here\n";
}

# -------------------------- infrastructure -------------------------

sub display_question {   my $question = shift; my %options = @_;
	# used by &ask and &confirm, but not by &choose ...
	&check_size();
	my ($firstline, @otherlines);
	if ($options{nofirstline}) {
		@otherlines = &fmt($question);
	} else {
		($firstline,$otherlines) = split (/\r?\n/, $question, 2);
		@otherlines = &fmt($otherlines);
		if ($firstline) { &puts("$firstline "); }
	}
	if (@otherlines) {
		&puts("\r\n", join("\r\n", @otherlines), "\r");
		&goto(1 + length $firstline, 0);
	}
	return scalar @otherlines;
}
sub erase_lines {  # leaves cursor at beginning of line $_[$[]
	&goto(0, $_[$[]); &puts("\e[J");
}
sub fmt { my $text = shift; my %options = @_;
	# Used by tiview, ask and confirm; formats the text within $maxcols cols
	my (@i_words, $o_line, @o_lines, $o_length, $last_line_empty, $w_length);
	my (@i_lines, $initial_space);
	@i_lines = split (/\r?\n/, $text);
	foreach $i_line (@i_lines) {
   	if ($i_line =~ /^\s*$/) {   # blank line ?
      	if ($o_line) { push @o_lines, $o_line; $o_line=''; $o_length=0; }
      	if (! $last_line_empty) { push @o_lines,""; $last_line_empty=1; }
      	next;
   	}
   	$last_line_empty = 0;

		if ($options{nofill}) {
			push @o_lines, substr($i_line, $[, $maxcols); next;
   	}
		if ($i_line =~ s/^(\s+)//) {   # line begins with space ?
			$initial_space = $1; $initial_space =~ s/\t/   /g;
      	if ($o_line) { push @o_lines, $o_line; }
      	$o_line = $initial_space; $o_length = length $initial_space;
   	} else {
			$initial_space = '';
		}

   	@i_words = split (' ', $i_line);
   	foreach $i_word (@i_words) {
      	$w_length = length $i_word;
      	if (($o_length + $w_length) > $maxcols) {
         	push @o_lines, $o_line;
				$o_line = $initial_space; $o_length = length $initial_space;
      	}
      	if ($w_length > $maxcols) {  # chop it !
				push @o_lines, substr($i_word,$[,$maxcols); next;
			}
      	if ($o_line) { $o_line .= ' '; $o_length += 1; }
      	$o_line .= $i_word; $o_length += $w_length;
   	}
	}
	if ($o_line) { push @o_lines, $o_line; }
	if ((scalar @o_lines) < $maxrows-2) { return (@o_lines);
	} else { return splice (@o_lines, $[, $maxrows-2);
	}
}
sub back_up {
	open(TTY, ">/dev/tty") || (warn "Can't write /dev/tty: $!\n", return 0);
	print TTY "\r\033[K\033[A\033[K";
	close TTY;
}
1;

__END__

=pod

=head1 NAME

Term::Clui.pm - Perl module offering a Command-Line User Interface

=head1 SYNOPSIS

	use Term::Clui;
	$chosen = &choose('A Title', @a_list);  # single choice
	@chosen = &choose('A Title', @a_list);  # multiple choice
	if (&confirm($text)) { &do_something(); };
	$answer = &ask($question);
	$answer = &ask($question,$suggestion);
	$password = &ask_password('Enter password : ');
	$newtext = &edit($title, $oldtext);
	&edit($filename);
	&view($title, $text)  # if $title is not a filename
	&view($textfile)  # if $textfile _is_ a filename

	&edit (&choose ('Edit which file ?', grep (-T, readdir D)));

=head1 DESCRIPTION

Term::Clui
offers a high-level user interface to give the user of
command-line applications a consistent "look and feel".
Its metaphor for the computer is as a human-like conversation-partner,
and as each question/response is completed it is summarised onto one line,
and remains on screen, so that the history of the session gradually
accumulates on the screen and is available for review, or for cut/paste.
This user interface can therefore be intermixed with
standard applications which write to STDOUT or STDERR,
such as I<make>, I<pgp>, I<rcs> etc.

For the user, I<&choose> uses arrow keys (or hjkl) and Return or q;
also SpaceBar for multiple choices.
I<&confirm> expects y, Y, n or N.
In general, ctrl-L redraws the (currently active bit of the) screen.
I<&edit> and I<&view> use the default EDITOR and PAGER if possible.  

It's fast, simple, and has few external dependencies.
It doesn't use I<curses> (which is a whole-of-screen interface);
it uses a small subset of vt100 sequences (up down left right normal
and reverse) which are very portable.

There is an associated file selector, Term::Clui::FileSelect

This is Term::Clui.pm version 1.22,
#COMMENT#.

=head1 WINDOW-SIZE

Term::Clui attempts to handle the WINCH signal.
If the window size is changed,
then as soon as the user enters the next keystroke (such as ctrl-L)
the current question/response will be redisplayed to fit the new size.

The first line of the question, the one which will remain on-screen, is
not re-formatted, but is left to be dealt with by the width of the window.
Subsequent lines are split into blank-separated words which are
filled into the available width; lines beginning with white-space
are treated as the beginning of a new indented paragraph,
individual words which will not fit onto one line are truncated,
and successive blank lines are collapsed into one.
If the question will not fit within the available rows, it is truncated.

If the available choice items in a I<&choose> overflow the screen,
the user is asked to enter 'clue' letters,
and as soon as the items matching them will fit onto the screen
they are displayed as a choice.

=head1 SUBROUTINES

=over 3

=item I<ask>( $question );  OR I<ask>( $question, $default );

Asks the user the question and returns a string answer,
with no newline character at the end.
If the optional second argument is present, it is offered to the user
as a default.
For the user, left and right arrow keys move backward and forward
through the string, delete and backspace erase the previous character,
ctrl-B moves to the beginning, ctrl-E to the end,
and ctrl-C, ctrl-D or ctrl-X clear the current string.

=item I<ask_password>( $question );

Does the same with no echo, as used for password entry.

=item I<choose>( $question, @list );

Displays the question, and formats the list items onto the lines beneath it.

If I<choose> is called in a scalar context,
the user can choose an item using arrow keys (or hjkl) and Return,
or cancel the choice with a 'q'.
I<choose> then returns the chosen item,
or I<undefined> if the choice was cancelled.

If I<choose> is called in an array context,
the user can also mark an item with the SpaceBar.
I<choose> then returns the list of marked items,
(including the item highlit when Return was pressed),
or an empty array if the choice was cancelled.

A DBM database is maintained of the question and its chosen response.
The next time the user is offered a choice with the same question,
if that response is still in the list it is highlighted
as the default; otherwise the first item is highlighted.
Different parts of the code, or different applications using I<Term::Clui.pm>
can therefore exchange defaults simply by using the same question words,
such as "Which printer ?".
Multiple choices are not remembered, as the danger exists
that the user might fail to notice some of the highlit items
(for example, all the items might not fit onto one screen).

The database I<~/.clui_dir/choices> or I<$ENV{CLUI_DIR}/choices>
is available to be read or written if lower-level manipulation is needed,
and the I<EXPORT_OK> routines I<&get_default>($question) and
I<&set_default>($question, $choice) should be used for this purpose,
as they handle DBM's problem with concurrent accesses.
The whole default database mechanism can be disabled by
I<CLUI_DIR=OFF> if you really want to :-(

If the items won't fit on the screen, the user is asked to enter
a substring as a clue. As soon as the matching items will fit,
they are displayed to be chosen as normal. If the user pressed "q"
at this choice, they are asked if they wish to change their substring
clue; if they reply "n" to this, choose quits and returns I<undefined>.

=item I<confirm>( $question );

Asks the question, takes 'y', 'n', 'Y' or 'N' as a response.
If the $question is multi-line, after the response, all but the first
line is erased, and the first line remains on-screen with I<Yes> or I<No>
appended after it; you should therefore try to arrange multi-line
questions so that the first line is the question in short form,
and subsequent lines are explanation and elaboration.
Returns true or false.

=item I<edit>( $title, $text );  OR  I<edit>( $filename );

Uses the environment variable EDITOR ( or I<vi> :-)
Uses RCS if directory RCS/ exists

=item I<sorry>( $message );

Similar to I<warn "Sorry, $message\n";>

=item I<inform>( $message );

Similar to I<warn "$message\n";> except that it doesn't add the
newline at the end if there already is one,
and it uses I</dev/tty> rather than I<STDERR> if it can.

=item I<view>( $title, $text );  OR  I<view>( $filename );

If the I<$text> is longer than a screenful, uses the environment
variable PAGER ( or I<less> ) to display it.
If it is one or two lines it just omits the title and displays it.
Otherwise it uses a simple built-in routine which expects either 'q'
or I<Return> from the user; if the user presses I<Return>
the displayed text remains on the screen and the dialogue continues
after it, if the user presses 'q' the text is erased.

=back

=head1 DEPENDENCIES

It requires Exporter, which is core Perl.
It uses Term::Size.pm if it's available;
if not, it tries `tput` before guessing 80x24.

=head1 ENVIRONMENT

The environment variable I<CLUI_DIR> can be used (by programmer or user)
to set the directory in which I<&choose> keeps its database of default choices.
The default directory (changed at version 1.17) is now I<~/.clui_dir>
and the whole default database mechanism can be disabled by
I<CLUI_DIR = OFF> if you really want to :-(

I<Clui.pm> also consults the environment variables
HOME, LOGDIR, EDITOR and PAGER, if they are set.

=head1 AUTHOR

Peter J Billam www.pjb.com.au/comp/contact.html

=head1 CREDITS

Based on some old perl 4 libraries, I<ask.pl>, I<choose.pl>,
I<confirm.pl>, I<edit.pl>, I<sorry.pl>, I<inform.pl> and I<view.pl>,
which were in turn based on some even older curses-based programs in I<C>.

=head1 SEE ALSO

Term::Clui::FileSelect ,
http://www.pjb.com.au/ , perl(1), http://www.cpan.org/SITES.html

=cut
