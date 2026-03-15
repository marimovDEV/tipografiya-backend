
from django.test import TestCase
from api.constructors import MailerBoxGenerator, get_generator

class MailerBoxGeneratorTest(TestCase):
    def test_simple_box_generation(self):
        """Test that generator runs without error for standard dimensions"""
        L, W, H = 20, 15, 5 # cm
        generator = get_generator('mailer_box', L, W, H, thickness=0.3)
        paths = generator.generate_paths()
        
        self.assertIn('cut', paths)
        self.assertIn('crease', paths)
        self.assertIn('safe', paths)
        
        # Verify SVG path content availability
        self.assertTrue(len(paths['cut']) > 0)
        self.assertTrue(len(paths['crease']) > 0)
        
        # Verify wrapper generation
        svg = generator._create_svg_wrapper(paths, 1000, 1000)
        self.assertIn('<svg', svg)
        self.assertIn('class="cut"', svg)
        self.assertIn('class="crease"', svg)
        self.assertIn('class="bleed"', svg) # Should be there even if empty path logic logic defaults? No, conditionally added

    def test_bend_allowance_calculation(self):
        """Verify the bend allowance logic exists"""
        generator = MailerBoxGenerator(10, 10, 10, thickness=3)
        # Expected BA = 1.57 * (3mm + 0.4*3mm) = 1.57 * 4.2 = 6.594mm
        expected_ba = 1.57 * (3.0 + (0.4 * 3.0))
        self.assertAlmostEqual(generator.bend_allowance, expected_ba, places=2)

    def test_knife_length_calculation(self):
        """Test knife length estimation"""
        generator = MailerBoxGenerator(10, 10, 5)
        lengths = generator.calculate_knife_length()
        self.assertIsNotNone(lengths['cut'])
        self.assertIsNotNone(lengths['crease'])
        self.assertTrue(lengths['cut'] > 0)
