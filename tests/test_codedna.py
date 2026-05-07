"""Tests for CodeDNA fingerprinting module."""

import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codevista.codedna import CodeDNA


class TestCodeDNA:
    def test_generate_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('import os\n\ndef hello():\n    print("hello")\n')
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            assert 'hash_patterns' in fp
            assert 'language_distribution' in fp
            assert 'naming_conventions' in fp
            assert 'comment_density' in fp
            assert 'total_files' in fp
            assert fp['total_files'] == 1

    def test_language_distribution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'a.py'), 'w') as f:
                f.write('x = 1\n')
            with open(os.path.join(tmpdir, 'b.js'), 'w') as f:
                f.write('const x = 1;\n')
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            langs = fp['language_distribution']
            assert 'Python' in langs
            assert 'JavaScript' in langs

    def test_complexity_distribution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('def f():\n    if x:\n        if y:\n            pass\n')
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            comp = fp['complexity_distribution']
            assert 'buckets' in comp
            assert comp['files_analyzed'] == 1

    def test_naming_conventions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('def my_func():\n    my_var = 1\n')
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            naming = fp['naming_conventions']
            assert naming['dominant'] == 'snake_case'

    def test_comment_density(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('# comment\ncode = 1\n')
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            cd = fp['comment_density']
            assert cd['overall_density'] > 0

    def test_compare_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('x = 1\n')
            dna = CodeDNA(tmpdir)
            fp1 = dna.generate_fingerprint()
            fp2 = dna.generate_fingerprint()
            result = dna.compare_fingerprints(fp1, fp2)
            assert result['overall_similarity'] >= 80

    def test_compare_different(self):
        with tempfile.TemporaryDirectory() as tmpdir1:
            with open(os.path.join(tmpdir1, 'test.py'), 'w') as f:
                f.write('x = 1\n')
            dna1 = CodeDNA(tmpdir1)
            fp1 = dna1.generate_fingerprint()

            with tempfile.TemporaryDirectory() as tmpdir2:
                with open(os.path.join(tmpdir2, 'app.js'), 'w') as f:
                    f.write('const x = 1;\n')
                dna2 = CodeDNA(tmpdir2)
                fp2 = dna2.generate_fingerprint()

                result = dna2.compare_fingerprints(fp1, fp2)
                assert 'overall_similarity' in result
                assert 'verdict' in result

    def test_barcode_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('x = 1\n')
            dna = CodeDNA(tmpdir)
            barcode = dna.generate_barcode()
            assert 'CodeDNA' in barcode
            assert 'Compact' in barcode

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'test.py'), 'w') as f:
                f.write('x = 1\n')
            dna = CodeDNA(tmpdir)
            dna.generate_fingerprint()

            save_path = os.path.join(tmpdir, 'fp.json')
            dna.save_fingerprint(save_path)
            assert os.path.isfile(save_path)

            loaded = dna.load_fingerprint(save_path)
            assert loaded['total_files'] == 1

    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dna = CodeDNA(tmpdir)
            fp = dna.generate_fingerprint()
            assert fp['total_files'] == 0

    def test_detect_clones(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            code = 'def hello():\n    print("world")\n'
            with open(os.path.join(tmpdir, 'a.py'), 'w') as f:
                f.write(code)
            with open(os.path.join(tmpdir, 'b.py'), 'w') as f:
                f.write(code)
            dna = CodeDNA(tmpdir)
            clones = dna.detect_clones()
            assert 'exact_clones' in clones
            assert 'near_clones' in clones


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
