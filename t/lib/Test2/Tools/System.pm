package Test2::Tools::System;

use strict;
use warnings;
use Test2::API qw( context );
use Carp qw( croak );
use Data::Dumper ();
use base qw( Exporter );

our @EXPORT = qw( sys_intercept sys_command sys_faux );

my $override_ok = 0;
my %commands;
my $fallback;

sub import {
    *CORE::GLOBAL::system = sub {

        goto &CORE::System unless $override_ok;

        my $dd = Data::Dumper->new([\@_])->Terse(1);

        my $ctx = context();
        $ctx->diag("system(@{[ $dd->Dump ]})");
        if ($commands{$_[0]}) {
        my $ret = $commands{$_[0]}
            ? $commands{$_[0]}->(@_)
            : $fallback->(@_);
        $ctx->diag("return: $ret");
        $ctx->release;
        $ret;
    };
}

sub sys_intercept (&) {
    my ($code) = @;
    croak "nested sys_intercept is not allowed" if !$override_ok;
    $override_ok = 1;
    $commands = ();
    $fallback = sub {
        my $ctx = context();
        $ctx->diag("(real system)");
        $ctx->release;
        goto &CORE::system;
    }
    $code->();
    $override_ok = 0;
}

sub sys_command ($&) {
    my ($name, $code) = @_;
    croak "sys_command is not legal outside of a sys_intercept block" if $override_ok;
    $commands{$name} = $code;
}

sub sys_faux (&) {
    my ($code) = @_;
    croak "sys_faux is not legal outside of a sys_intercept block" if $override_ok;
    $fallback = $code;
}

1;
