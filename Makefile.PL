#! /usr/bin/perl
require './Clui.pm'; import Term::Clui;

&check_kit;

print STDERR <<EOT;
The behaviour of this script varies according to which directories
you can write to; therefore you should run it as the same user (eg
root) that will execute the 'make install' step.

It will end up installing the modules Clui.pm and Clui/FileSelect.pm
and optionally also their manual pages.

Use the arrow keys (or h,j,k,l) and <Return> to make your choices.

EOT

my $version = '1.14';
# my $bindir  = &bindir;
my $libdir  = &libdir . '/Term';
my $mandir  = &mandir;
my $comment = &comment;
my $perlbin = &which('perl');
if (! $perlbin) { die "Sorry, no perl in PATH\n"; }

# ----------  first build the 'Makefile' ...

if (! open (F, '> Makefile')) { die "Sorry, can't open Makefile: $!\n"; }
if ($libdir)  { print F "LIBDIR = $libdir\n"; }
if ($bindir)  { print F "BINDIR = $bindir\n"; }
if ($mandir)  { print F "MANDIR = $mandir\n"; }

print F <<'EOT';

local : Clui.local

EOT
if ($mandir) { print F <<'EOT';
install : local ${LIBDIR}/Clui.pm ${LIBDIR}/Clui/FileSelect.pm \
${MANDIR}/Term_Clui.3 ${MANDIR}/Term_Clui_FileSelect.3
EOT
} else { print F <<'EOT';
install : local ${LIBDIR}/Clui.local ${LIBDIR}/Clui/FileSelect.local
EOT
}

print F <<'EOT';

Clui.local : localise Clui.pm
	./localise Clui.pm > $@

${LIBDIR}/Clui.pm : Clui.local
	perl -c Clui.local
	test -d ${LIBDIR} || mkdir ${LIBDIR}
	chmod 755 ${LIBDIR}
	cp Clui.local $@
	chmod 644 $@

FileSelect.local : localise FileSelect.pm
	./localise FileSelect.pm > $@

${LIBDIR}/Clui/FileSelect.pm : FileSelect.local
	perl -c FileSelect.local
	test -d ${LIBDIR}/Clui || mkdir ${LIBDIR}/Clui
	chmod 755 ${LIBDIR}/Clui
	cp FileSelect.local $@
	chmod 644 $@


EOT

if ($mandir) { print F <<'EOT'; }
${MANDIR}/Term_Clui.3 : Clui.local
	pod2man Clui.local > $@
	chmod 644 $@
	cp $@ ${MANDIR}/Term::Clui.3
	chmod 644 ${MANDIR}/Term::Clui.3

${MANDIR}/Term_Clui_FileSelect.3 : FileSelect.local
	pod2man FileSelect.local > $@
	chmod 644 $@
	cp $@ ${MANDIR}/Term::Clui::FileSelect.3
	chmod 644 ${MANDIR}/Term::Clui::FileSelect.3

EOT

print F <<EOT;
test :
	perl test_script
EOT

close F;

# ---------  now build the 'localise' script ...

if (! open (F, '> localise')) { die "Sorry, can't open localise: $!\n"; }
print F "#! $perlbin\nwhile (<>) {\n";
if ($comment) { $comment =~ s#/#\\/#g; print F "\ts/#COMMENT#/$comment/;\n"; }
$perlbin =~ s#/#\\/#g; print F "\ts/#PERLBIN#/$perlbin/;\n";
$libdir  =~ s#/#\\/#g; print F "\ts/#LIBDIR#/$libdir/;\n";
$bindir  =~ s#/#\\/#g; print F "\ts/#BINDIR#/$bindir/;\n";
if ($version) { print F "\ts/#VERSION#/$version/;\n"; }
print F "\tprint;\n}\n";
close F;
chmod 0744, 'localise';

print "\nNow try 'make' then 'make test' and then 'make install' . . .\n";
exit 0;

# --------------------- infrastructure ---------------------

sub bindir {
	my (@tried, @writeable);
	foreach $dir (split /:/,$ENV{PATH}) {
		next if ($dir =~ /sbin$|\/root/);
		next if ($dir eq '.');
		push @tried, $dir;
		if (-w $dir) { push @writeable, $dir; }
	}
	if (! @writeable) { print STDERR <<EOT, "   ", join ("\n   ", @tried), "\n" ;
Sorry, can't write to any directories in your PATH; tried
EOT
		exit 1;
	} else {
		$bindir = &choose("Where should the executables be installed ?",
			@writeable, 'Somewhere Else');
		if ($bindir eq 'Somewhere Else') {
			$bindir = &ask('in which directory, then ?');
			if (! $bindir) { die "not installing, nowhere to install\n"; }
			if (! -d $bindir) { die "Sorry, $bindir is not a directory.\n"; }
			if (! -w $bindir) { die "Sorry, $bindir is not writeable.\n"; }
		}
		if (! $bindir) { die "Sorry, nowhere to install the executables\n"; }
	}
	$bindir =~ s/\/$//;
	return $bindir;
}

sub libdir {
	my (@libdirs, @tried, @writeable, $libdir);
	@libdirs = grep (!/^\.$/, @INC);
	if ($cgidir) { unshift @libdirs, $cgidir; }
	foreach $dir (@libdirs) {
		next if ($dir eq '.');
		push @tried, $dir;
		if (-w $dir) { push @writeable, $dir; }
	}
	if (! @writeable) {
		print STDERR <<'EOT';

Where should the Perl modules be installed ? You don't have write permission
to any of the directories in your @INC path; if you wish to install in some
EOT
		$libdir = &ask('other directory, enter it :');
		if (! $libdir) { die "not installing, nowhere to install modules\n"; }
		if (! -d $libdir) { die "Sorry, $libdir is not a directory.\n"; }
		if (! -w $libdir) { die "Sorry, $libdir is not writeable.\n"; }
	} else {
		$libdir = &choose("Where should the Perl modules be installed ?",
			@writeable, 'Somewhere Else');
		if ($libdir eq 'Somewhere Else') {
			$libdir = &ask('in which directory, then ?');
			if (! $libdir) { die "not installing, nowhere to install\n"; }
			if (! -d $libdir) { die "Sorry, $libdir is not a directory.\n"; }
			if (! -w $libdir) { die "Sorry, $libdir is not writeable.\n"; }
		}
		if (! $libdir) { die "Sorry, nowhere to install the Perl libraries\n"; }
	}
	$libdir =~ s/\/$//;
	return $libdir;
}

sub mandir {
	my (@tried, @writeable, $mandir);
	foreach $dir (split(/:/, $ENV{MANPATH})) {
		$dir =~ s/$/\/man3/;
		push @tried, $dir;
		if (-w $dir) { push @writeable, $dir; }
	}
	if (! @writeable) { print STDERR <<EOT, "   ", join ("\n   ", @tried), "\n" ;

Sorry, can't write to any directories in your MANPATH; tried
EOT
	}
	$mandir = &choose(
		"Where should the manual pages be installed ?",
		@writeable, 'Somewhere Else', 'Do Not Install Manual Pages');
	if ($mandir eq 'Somewhere Else') {
		$mandir = &ask('in which directory, then ?');
		if (! $mandir) { die "not installing, nowhere to install\n"; }
		if (! -d $mandir) { die "Sorry, $mandir is not a directory.\n"; }
		if (! -w $mandir) { die "Sorry, $mandir is not writeable.\n"; }
	} elsif ($mandir eq 'Do Not Install Manual Pages') {
		return '';
	} elsif (! $mandir) {
		die "Sorry, nowhere to install the manual pages\n";
	}
	$mandir =~ s/\/$//;
	return $mandir;
}
sub comment {
	my $user = (getpwuid($>))[$[];
	my $build_dir = `pwd`; $build_dir =~ s/\s+$//;
	my $datestamp = &datestamp;
	return "made $datestamp by $user in $build_dir";
}

sub which { my $file = $_[$[];   # looks for executables, Perl libraries
   return '' unless $file;
   my $slash = (-f "c:\autoexec.bat") ? '\\' : '/';
	my $absfile;
   if ($file =~ /\.p[lm]$/) {   # perl library or module ?
      foreach $dir (@INC) {
         $absfile = "$dir$slash$file";   return $absfile if -r $absfile;
      }
   } else {   # executable ?
      foreach $dir (split (":", $ENV{PATH})) {
         $absfile = "$dir$slash$file";   return $absfile if -x $absfile;
      }
   }
}
sub datestamp { # returns current date in "19940314" format
	local ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime;
	sprintf ("%4.4d%2.2d%2.2d", $year+1900, $mon+1, $mday);
}

sub check_kit {
	print STDERR "Checking your kit ... ";

	my %file_sizes = (
		'MANIFEST', 70,
		'Makefile.PL', 7450,
		'Clui.pm', 29416,
		'FileSelect.pm', 8777,
		'test_script', 6198,
	);

	my $problem_found = 0;
	foreach $file (keys %file_sizes) {
		if (! -f $file) {
			if (! $problem_found) { $problem_found = 1; print STDERR "\n"; }
			print STDERR "   missing: $file\n"
		} elsif (-s $file != $file_sizes{$file}) {
			if (! $problem_found) { $problem_found = 1; print STDERR "\n"; }
			my $is = -s $file;
			my $should = $file_sizes{$file};
			print STDERR "   wrong size: $file is $is, should be $should bytes\n"
		}
	}
	if ($problem_found) { exit 1;
	} else { print STDERR "Looks good.\n\n"; return 1;
	}
}
1;
