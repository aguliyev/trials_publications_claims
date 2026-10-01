"""Instructions and criteria for scoring claim support."""

SUPPORT_QUESTION = {
    'instructions': (
        'Does the source support the claim that the named intervention worked for the named disease? '
        'Evaluate reported outcomes, not study objectives or mere mentions. '
        'Use unaddressed when there is insufficient evidence in the source.'
    ),
    'criteria': {
        'supports': 'The source reports a positive outcome supporting the claim.',
        'contradicts': 'The source reports an outcome contradicting the claim.',
        'unaddressed': 'The source does not establish whether the claim is true.',
    },
}
