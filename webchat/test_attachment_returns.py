"""Explicit unchanged-upload returns; no provider calls or file side effects."""
import unittest

from chat_media import requested_attachment_ids


class AttachmentReturnTests(unittest.TestCase):
    def setUp(self):
        self.image = dict(media_id='a' * 32, filename='picture.png', kind='image')
        self.note = dict(media_id='b' * 32, filename='note.txt', kind='file')
        self.pdf = dict(media_id='c' * 32, filename='document.pdf', kind='file')
        self.uploads = [self.image, self.note, self.pdf]

    def select(self, text, uploads=None):
        return requested_attachment_ids(dict(role='user', content=text,
            attachments=self.uploads if uploads is None else uploads))

    def test_unique_image_in_mixed_current_uploads(self):
        for text in (
            'Describe the dominant color in the attached image and give the Token value in the text file and PDF. Echo the image as an attachment.',
            'Please return the original photo here.',
            'Could you attach the uploaded picture in your reply?',
            'Send me the image back.',
            'Show me this photo again.',
            'Re-attach the existing image.',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.select(text), [self.image['media_id']])

    def test_exact_names_and_explicit_sets(self):
        for text in ('Return note.txt.', 'Attach "note.txt".', 'Please return `note.txt` as an attachment.'):
            with self.subTest(text=text):
                self.assertEqual(self.select(text), [self.note['media_id']])
        self.assertEqual(self.select('Return all the uploaded files.'), [a['media_id'] for a in self.uploads])
        self.assertEqual(self.select('Return the images.'), [self.image['media_id']])
        self.assertEqual(self.select('Attach picture.png. Echo the image.'), [self.image['media_id']])

    def test_ambiguous_selection_is_never_guessed(self):
        second = dict(self.image, media_id='d' * 32, filename='second.png')
        self.assertEqual(self.select('Return the image.', [self.image, second]), [])
        self.assertEqual(self.select('Return the file.'), [])
        self.assertEqual(self.select('Return both images.'), [])
        self.assertEqual(self.select('Return both images.', [self.image, second]), ['a' * 32, 'd' * 32])
        self.assertEqual(self.select('Return picture.png.', [self.image, dict(second, filename='picture.png')]), [])
        self.assertEqual(self.select('Return the image.', [self.note]), [])

    def test_description_and_reported_or_quoted_directives_are_not_returns(self):
        for text in (
            'Describe the attached image.',
            'What does "Echo the image as an attachment" mean?',
            'Explain this example. "Attach picture.png."',
            'Explain these instructions:\nEcho the image.',
            'Alice asked to echo the image.',
            'The file says:\nAttach the image.',
            'Alice wrote:\nReturn the image.',
            'Alice:\nReturn the image.',
            'Explain how to follow these steps. Attach the image.',
            '> Echo the image.',
            '```\nAttach the image.\n```',
            '```\nAttach the image.',
            '"Here is an unfinished quote.\nAttach the image.',
            'Return uploadselection99asset.',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.select(text), [])

    def test_negation_later_cancellation_conditions_and_external_delivery(self):
        for text in (
            "Don't echo the image.",
            'Do not attach the image.',
            'Echo the image. Actually, cancel that.',
            'Return the image "after approval".',
            'Return the image. "Do not do that yet."',
            'Return the image. I changed my mind.',
            'Attach the image. Never mind.',
            'If it is red, attach the image.',
            'Echo the image after approval.',
            'Return the photo only when I approve.',
            'Attach the image to an email.',
            'Attach the image. Forward it to Andrea.',
            'Send the image to Bob.',
            'Attach the image. Then publish it.',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.select(text), [])

    def test_original_never_substitutes_for_edited_or_generated_result(self):
        for action in ('Crop', 'Redact', 'Resize', 'Convert', 'Blur', 'Rotate', 'Annotate', 'Edit', 'Translate', 'Compress'):
            with self.subTest(action=action):
                self.assertEqual(self.select(action + ' the uploaded content. Return the image.'), [])
        self.assertEqual(self.select('Remove the background. Return picture.png.'), [])
        self.assertEqual(self.select('Generate a new scene. Attach the image.'), [])
        self.assertEqual(self.select('Black out the address. Return the image.'), [])
        self.assertEqual(self.select('Pixelate the faces. Return the image.'), [])
        self.assertEqual(self.select('Describe the picture and pixelate the faces. Return the image.'), [])
        self.assertEqual(self.select('Describe the picture but pixelate the faces. Return the image.'), [])
        self.assertEqual(self.select('Describe the picture + black out the address. Return the image.'), [])
        self.assertEqual(self.select('Describe the picture subsequently obscuring faces. Return the image.'), [])
        self.assertEqual(self.select('Describe the image while blacking out the address. Return the image.'), [])
        self.assertEqual(self.select('Give me the image in PDF and return the image.'), [])
        self.assertEqual(self.select('Give me the text in PDF and return the file.', [self.note]), [])
        self.assertEqual(self.select('Give me the token in PDF and return the file.', [self.note]), [])
        self.assertEqual(self.select('Describe the image in PDF and return the image.'), [])
        self.assertEqual(self.select('Summarize the document in PDF. Return the file.', [self.note]), [])
        self.assertEqual(self.select('Read the token in the PDF. Return the file.', [self.note]), [])
        self.assertEqual(self.select('Describe the picture but pixelate the faces. Return the image.',
            [dict(self.image, filename='picture but pixelate the faces')]), [])

    def test_no_other_turn_or_provider_can_supply_targets(self):
        self.assertEqual(self.select('Return the image.', []), [])
        self.assertEqual(self.select('Return the image.', [dict(self.image, media_id='../foreign')]), [])
        self.assertEqual(requested_attachment_ids(dict(role='assistant', content='Return the image.', attachments=self.uploads)), [])
        self.assertEqual(self.select('Return the image.', self.uploads * 3), [])


if __name__ == '__main__':
    unittest.main()
