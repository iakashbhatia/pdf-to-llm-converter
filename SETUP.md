# Setup Guide for GitHub

## Initial Setup

1. **Initialize Git repository** (if not already done):
```bash
git init
git add .
git commit -m "Initial commit: PDF-to-LLM Converter"
```

2. **Create a new repository on GitHub**:
   - Go to https://github.com/new
   - Name: `pdf-to-llm-converter`
   - Description: "Convert large PDFs to structured markdown for LLM ingestion"
   - Choose Public or Private
   - Don't initialize with README (we already have one)
   - Click "Create repository"

3. **Link local repository to GitHub**:
```bash
git remote add origin https://github.com/YOUR_USERNAME/pdf-to-llm-converter.git
git branch -M main
git push -u origin main
```

## Repository Settings

### Enable GitHub Actions
- Go to repository Settings → Actions → General
- Enable "Allow all actions and reusable workflows"
- This will run tests automatically on push/PR

### Add Topics (Optional)
Add these topics to help others discover your project:
- `pdf`
- `markdown`
- `ocr`
- `llm`
- `document-processing`
- `tesseract`
- `python`
- `legal-documents`

### Create Releases (Optional)
When ready to release:
```bash
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0
```

Then create a release on GitHub with release notes.

## Next Steps

1. **Update README.md**:
   - Replace `YOUR_USERNAME` with your actual GitHub username
   - Add screenshots or examples if desired

2. **Test the installation**:
```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/pdf-to-llm-converter.git
cd pdf-to-llm-converter

# Install
pip install -e .

# Test
pdf-to-llm --help
```

3. **Share your project**:
   - Add the GitHub URL to your profile
   - Share on social media or relevant communities
   - Consider adding to awesome lists

## Maintenance

- Respond to issues and pull requests
- Keep dependencies updated
- Add new features based on user feedback
- Write blog posts or tutorials about usage
