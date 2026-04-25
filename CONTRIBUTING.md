# Contributing to Zendaya AI Assistant

Thank you for your interest in contributing to Zendaya AI Assistant! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 16+
- Flutter 3.10+
- Unity 2022.3+ (for AR client development)
- Git

### Development Environment Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/zendaya-ai-assistant.git
   cd zendaya-ai-assistant
   ```

2. **Backend Setup**
   ```bash
   cd zendaya-backend
   pip install poetry
   poetry install
   cp .env.example .env
   # Configure your API keys in .env
   ```

3. **Frontend Setup**
   ```bash
   # Web Dashboard
   npm install
   
   # Flutter Client
   cd zendaya-flutter-client
   flutter pub get
   ```

4. **Run Tests**
   ```bash
   # Backend tests
   cd zendaya-backend
   poetry run pytest
   
   # Frontend tests
   npm test
   ```

## 🎯 How to Contribute

### Reporting Issues

1. **Search Existing Issues**: Check if the issue already exists
2. **Use Issue Templates**: Follow the provided templates
3. **Provide Details**: Include steps to reproduce, expected behavior, and system info
4. **Add Labels**: Help categorize the issue (bug, feature, enhancement)

### Submitting Pull Requests

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow the coding standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   # Run all tests
   poetry run pytest
   npm test
   flutter test
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 Coding Standards

### Python (Backend)

- **Formatting**: Use Black with line length 88
- **Imports**: Use isort for import sorting
- **Linting**: Follow flake8 rules
- **Type Hints**: Use type hints for all functions
- **Docstrings**: Use Google-style docstrings

```python
def example_function(param: str) -> Dict[str, Any]:
    """
    Example function with proper formatting.
    
    Args:
        param: Description of parameter
        
    Returns:
        Dictionary with results
    """
    return {"result": param}
```

### TypeScript (Web Dashboard)

- **Formatting**: Use Prettier
- **Linting**: Follow ESLint rules
- **Components**: Use functional components with hooks
- **Types**: Define proper TypeScript interfaces

```typescript
interface ExampleProps {
  title: string;
  onAction: (value: string) => void;
}

const ExampleComponent: React.FC<ExampleProps> = ({ title, onAction }) => {
  return <div>{title}</div>;
};
```

### Dart (Flutter Client)

- **Formatting**: Use `flutter format`
- **Linting**: Follow `flutter analyze` rules
- **State Management**: Use Provider or BLoC pattern
- **Widgets**: Prefer composition over inheritance

```dart
class ExampleWidget extends StatelessWidget {
  final String title;
  final VoidCallback onTap;

  const ExampleWidget({
    Key? key,
    required this.title,
    required this.onTap,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Text(title),
    );
  }
}
```

### C# (Unity AR Client)

- **Formatting**: Follow Unity C# conventions
- **Namespaces**: Use `ZendayaAR` namespace
- **Components**: Inherit from MonoBehaviour when needed
- **Performance**: Use object pooling for dynamic objects

```csharp
namespace ZendayaAR
{
    public class ExampleComponent : MonoBehaviour
    {
        [Header("Configuration")]
        public float exampleValue = 1.0f;
        
        private void Start()
        {
            // Initialization code
        }
    }
}
```

## 🧪 Testing Guidelines

### Backend Tests

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test API endpoints
- **Mocking**: Mock external services (Gemini, ElevenLabs, etc.)
- **Coverage**: Aim for >80% test coverage

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_chat_endpoint():
    # Test implementation
    pass
```

### Frontend Tests

- **Component Tests**: Test React components
- **Widget Tests**: Test Flutter widgets
- **Integration Tests**: Test user flows
- **Snapshot Tests**: Prevent UI regressions

### Unity Tests

- **Play Mode Tests**: Test runtime behavior
- **Edit Mode Tests**: Test editor functionality
- **Performance Tests**: Monitor frame rates and memory

## 📚 Documentation

### Code Documentation

- **Inline Comments**: Explain complex logic
- **Function Documentation**: Document parameters and return values
- **API Documentation**: Use FastAPI's automatic documentation
- **README Updates**: Keep README.md current

### Architecture Documentation

- **System Design**: Document major architectural decisions
- **API Changes**: Document breaking changes
- **Migration Guides**: Help users upgrade

## 🔄 Development Workflow

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Critical fixes
- `docs/description` - Documentation updates

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks

### Pull Request Process

1. **Title**: Use descriptive titles
2. **Description**: Explain what and why
3. **Testing**: Describe how you tested
4. **Screenshots**: Include UI changes
5. **Breaking Changes**: Document any breaking changes

## 🏷️ Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Improvements to documentation
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `priority: high` - High priority issues
- `backend` - Backend-related issues
- `frontend` - Frontend-related issues
- `ar-client` - Unity AR client issues

## 🎯 Areas for Contribution

### High Priority

- **Device Control**: Add support for new device types
- **Voice Recognition**: Improve accuracy and language support
- **Performance**: Optimize response times and resource usage
- **Testing**: Increase test coverage
- **Documentation**: Improve user guides and API docs

### Medium Priority

- **UI/UX**: Enhance user interfaces
- **Accessibility**: Improve accessibility features
- **Internationalization**: Add multi-language support
- **Mobile Features**: Enhance Flutter client capabilities

### Low Priority

- **Integrations**: Add new third-party integrations
- **Themes**: Create new UI themes
- **Examples**: Add more usage examples
- **Tools**: Development and deployment tools

## 🤝 Community Guidelines

### Code of Conduct

- **Be Respectful**: Treat everyone with respect
- **Be Inclusive**: Welcome contributors from all backgrounds
- **Be Constructive**: Provide helpful feedback
- **Be Patient**: Help newcomers learn

### Communication

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Request Reviews**: For code feedback
- **Documentation**: For usage questions

## 🏆 Recognition

Contributors will be recognized in:

- **README.md**: Contributors section
- **Release Notes**: Major contributions
- **GitHub**: Contributor graphs and statistics

## 📞 Getting Help

If you need help:

1. **Check Documentation**: README, Wiki, API docs
2. **Search Issues**: Look for similar problems
3. **Ask Questions**: Use GitHub Discussions
4. **Join Community**: Connect with other contributors

Thank you for contributing to Zendaya AI Assistant! 🚀