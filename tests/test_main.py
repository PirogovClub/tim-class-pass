from tim_class_pass.main import main


def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "Hello from" in captured.out
