use lib 't/lib';
use Test2::V0 -no_srand => 1;
use Test2::Tools::System;
use ok 'Term::Clui';

subtest 'edit' => sub {

    sys_intercept {

        edit();
        ok;
    
    }

};

done_testing;
