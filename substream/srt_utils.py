import logging
from typing import (
    Iterable,
    Iterator,
    Sequence,
    Text,
    TextIO,
)

from speech_utils import (
    Word,
    read_words,
)

Subtitle = Sequence[Word]  # see speech_utils.Word

__all__ = ['Subtitle', 'words_to_srt', 'jsonl_to_srt']


def words_to_srt(words: Iterable[Word], srt_file: TextIO) -> None:
    """
    Converts speech_utils.Word objects to a .srt, optionally dumping word
    timing metadata to .jsonl format.

    :arg words: Word objects
                  (eg. a speech_utils.audio_to_words() Iterator)
    :arg srt_file: .srt file to write output to
    """
    logger = logging.getLogger('words_to_srt')
    logger.info(f'Writing subtitles to {srt_file.name}')

    # All that follow are generators until _write_srt. _write_srt pulls the
    # items through the pipeline from the source and 'drives' the pipeline.

    # Build the subtitle sequences from the words.
    subtitles = _words_to_subtitles(words)

    # Adjust the subtitles durations.
    subtitles = _adjust_duration(subtitles)

    # Write the subtitles sequences to an srt file.
    _write_srt(subtitles, srt_file)

    logger.info('Write complete')


def jsonl_to_srt(jsonl_file: TextIO, srt_file: TextIO) -> None:
    """
    Converts a .jsonl dump file to .srt format.

    :arg jsonl_file: input .jsonl file containing word timings
    :arg srt_file: output .srt file
    """
    words_to_srt(read_words(jsonl_file), srt_file)


def _words_to_subtitles(words: Iterable[Word],
                        split_on_pause_gt: float = 1.0,
                        split_on_length_gt: int = 32,
                        ) -> Iterator[Subtitle]:
    """
    :yields: Iterables of speech_utils.Records (sentence subtitles) split on:
        * punctuation (.?!)
        * pause between words

    :arg words: An Iterable of speech_utils.Word representing word timing.
    :param split_on_pause_gt: split on pause between words greater than
           this.
    """
    logger = logging.getLogger('words_to_srt')
    logger.info(f'Converting words to subtitles. Length per line {split_on_length_gt}')

    allowed_lines = 2

    subtitle = []  # a buffer for Words that gets yielded on certain conditions
    len_line = 0
    line_index = 0

    for word in words:
        add_line = False
        # Is the length of line more than threshold number of chars
        # or is sentence ending?
        if len_line + len(word["word"]) > split_on_length_gt:
            add_line = True
        elif word['word'].endswith(('.', '?', '!')):
            add_line = True
            subtitle.append(word)
            word = None

        if add_line:
            # Is already number of lines available for a timecode? (Normally 2 lines)
            # If yes, add to subtitle list (against a timecode)
            if line_index + 1 == allowed_lines:
                yield subtitle
                subtitle = []
                len_line = 0
                line_index = 0
            else:
                # Another line is possible. Add a newline character
                subtitle[-1]['word'] = subtitle[-1]['word'] + "\r\n"
                len_line = 0
                line_index = line_index + 1

        if word is not None:
            word['word'] = word['word'] + ' '
            len_line = len_line + len(word['word'])
            subtitle.append(word)

    if subtitle and len(subtitle) > 0:
        yield subtitle


def _adjust_duration(subtitles: Iterator[Subtitle],
                     min_sub_duration: float = 1.0,
                     ) -> Iterator[Subtitle]:
    """
    :yields: subtitles modified so that their minimum length is at least
             |min_sub_duration| seconds without overlapping the next subtitle.
    :arg subtitles: a Iterator of Subtitles
    :param min_sub_duration: minimum subtitle duration in sec. Default 1.0
    """

    prev_sub = next(subtitles)  # init with first subtitle in subtitles
    this_sub = None  # holds the 'cnrr
    for this_sub in subtitles:
        prev_sub_duration = prev_sub[-1]['end_time'] - prev_sub[0]['start_time']
        if prev_sub_duration >= min_sub_duration:
            # great, nothing to do, pass prev_sub straight through
            # and save this_sub as prev_sub for the next iteration.
            yield prev_sub
            prev_sub = this_sub
        else:
            # fix the end time, yield, and set prev_sub to this_sub
            prev_start_plus_min = prev_sub[0]['start_time'] + min_sub_duration
            if prev_start_plus_min > this_sub[0]['start_time']:
                prev_sub[-1]['end_time'] = this_sub[0]['start_time']
            else:
                prev_sub[-1]['end_time'] = prev_start_plus_min
            yield prev_sub
            prev_sub = this_sub
    if this_sub:
        yield this_sub


def _write_srt(subtitles: Iterable[Subtitle],
               srt_file: TextIO) -> None:
    """
    Writes an _write_srt file from an iterable of substream.Subtitle

    :arg subtitles: an iterable of Subtitles,
    :arg srt_file: .srt file object in text mode
    """

    for i, fragment in enumerate(subtitles):
        srt_start_time = _srt_fmt_time(fragment[0]['start_time'])
        srt_end_time = _srt_fmt_time(fragment[-1]['end_time'])
        sentence = ''.join(record['word'] for record in fragment)

        srt_file.write(str(i + 1) + '\n')
        srt_file.write(srt_start_time + ' --> ' + srt_end_time + '\n')
        srt_file.write(sentence + '\n')
        srt_file.write('\n')


def _srt_fmt_time(sec: float) -> Text:
    return '{:02}:{:02}:{:02},{:03}'.format(
        int(sec // 3600),
        int((sec % 3600) // 60),
        int(sec % 60 // 1),
        int((sec % 1) * 1000),
    )
