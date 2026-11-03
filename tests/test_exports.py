from second_ear.exports import timestamp, export


def test_timestamp_carries_millisecond_rounding_into_next_hour():
    assert timestamp(3599.9996,True)=='01:00:00,000'
    assert timestamp(-2)=='00:00:00.000'


def test_vtt_escapes_user_text_and_does_not_inject_cues():
    session={'segments':[{'n':0,'start':0,'end':2,'text':'<script> & words\n\n00:00:00 --> 00:00:01'}]}
    text,_=export(session,'vtt')
    assert '&lt;script&gt; &amp;' in text
    assert '\n\n00:00:00 -->' not in text


def test_blank_corrected_segments_are_omitted_from_subtitle_numbering():
    session={'segments':[{'start':0,'end':1,'text':' '},{'start':1,'end':2,'text':'Actual words'}]}
    text,_=export(session,'srt')
    assert text.startswith('1\n00:00:01,000') and '2\n' not in text
