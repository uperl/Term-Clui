use ExtUtils::MakeMaker;

WriteMakefile(
	NAME      => 'Term::Clui',
	VERSION_FROM => 'Clui.pm',
	AUTHOR    => 'PJB, Peter Billam, www.pjb.com.au/comp/contact.html',
	ABSTRACT  => 'Command-Line User Interface on /dev/tty',
	dist      => {COMPRESS=>'gzip -9f', SUFFIX => 'gz'},
);
