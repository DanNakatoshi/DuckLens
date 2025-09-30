# Test linting
.\tasks.ps1 lint

.\tasks.ps1 format
# Test type checking (this might show errors since we haven't written code yet)
.\tasks.ps1 type-check

# Test the test suite
.\tasks.ps1 test

