"""Generate only synthetic normalizer-contract inputs in a new directory."""
import importlib.util
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[1] / 'xlsx/make_sample.py'
spec = importlib.util.spec_from_file_location('synthetic_xlsx_writer', source)
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    writer.build(output/'data.xlsx', rows=[['ID'], ['0004711'], ['4711']], sheet_name='Data')
    writer.build(output/'header-only.xlsx', rows=[['ID']], sheet_name='Data')
    here=Path(__file__).resolve().parent
    for name in ('valid.json','invalid-rule.json','missing-column.json'):
        (output/name).write_bytes((here/name).read_bytes())


if __name__=='__main__':
    build(Path(sys.argv[1]))
